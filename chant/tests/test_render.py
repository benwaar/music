"""Tests for chant.render — MIDI pipeline."""

from __future__ import annotations

import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from chant.render import (
    events_to_midi,
    hz_to_midi_note,
    ms_to_midi_ticks,
    render_to_wav,
    _write_vlq,
    _volume_to_cc,
    _duty_to_cc,
    MIDI_PPQ,
)
from chant.schema import NoteEvent, Waveform


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _note(
    pitch_hz: float = 440.0,
    duration_ms: float = 120.0,
    channel: int = 0,
    waveform: Waveform | None = None,
    volume: float | None = None,
    duty_cycle: float | None = None,
) -> NoteEvent:
    return NoteEvent(
        pitch_hz=pitch_hz,
        duration_ms=duration_ms,
        channel=channel,
        waveform=waveform,
        volume=volume,
        duty_cycle=duty_cycle,
    )


# ---------------------------------------------------------------------------
# hz_to_midi_note
# ---------------------------------------------------------------------------

class TestHzToMidiNote:
    def test_a4_is_69(self):
        assert hz_to_midi_note(440.0) == 69

    def test_middle_c_is_60(self):
        assert hz_to_midi_note(261.63) == 60

    def test_a3_is_57(self):
        assert hz_to_midi_note(220.0) == 57

    def test_a5_is_81(self):
        assert hz_to_midi_note(880.0) == 81

    def test_zero_hz_returns_0(self):
        assert hz_to_midi_note(0.0) == 0

    def test_negative_hz_returns_0(self):
        assert hz_to_midi_note(-100.0) == 0

    def test_very_high_clamps_to_127(self):
        assert hz_to_midi_note(100_000.0) == 127

    def test_very_low_clamps_to_0(self):
        assert hz_to_midi_note(1.0) == 0


# ---------------------------------------------------------------------------
# ms_to_midi_ticks
# ---------------------------------------------------------------------------

class TestMsToMidiTicks:
    def test_positive_duration(self):
        ticks = ms_to_midi_ticks(100.0)
        assert ticks >= 1

    def test_zero_returns_1(self):
        assert ms_to_midi_ticks(0.0) == 1

    def test_negative_returns_1(self):
        assert ms_to_midi_ticks(-50.0) == 1

    def test_one_beat_at_120bpm(self):
        # 500ms = 1 beat at 120 BPM = MIDI_PPQ ticks
        ticks = ms_to_midi_ticks(500.0)
        assert ticks == MIDI_PPQ


# ---------------------------------------------------------------------------
# Volume / duty CC conversion
# ---------------------------------------------------------------------------

class TestCcConversion:
    def test_volume_none_returns_100(self):
        assert _volume_to_cc(None) == 100

    def test_volume_1_returns_127(self):
        assert _volume_to_cc(1.0) == 127

    def test_volume_0_returns_0(self):
        assert _volume_to_cc(0.0) == 0

    def test_volume_clamps_above(self):
        assert _volume_to_cc(2.0) == 127

    def test_volume_clamps_below(self):
        assert _volume_to_cc(-0.5) == 0

    def test_duty_none_returns_64(self):
        assert _duty_to_cc(None) == 64

    def test_duty_0_5_returns_64(self):
        assert _duty_to_cc(0.5) == 64


# ---------------------------------------------------------------------------
# VLQ encoding
# ---------------------------------------------------------------------------

class TestVlq:
    def test_zero(self):
        assert _write_vlq(0) == b"\x00"

    def test_127(self):
        assert _write_vlq(127) == b"\x7f"

    def test_128(self):
        assert _write_vlq(128) == b"\x81\x00"

    def test_480(self):
        # 480 = 0x1E0 → VLQ: 0x83 0x60
        result = _write_vlq(480)
        assert result == b"\x83\x60"


# ---------------------------------------------------------------------------
# events_to_midi — structure
# ---------------------------------------------------------------------------

class TestEventsToMidi:
    def test_empty_returns_valid_midi(self):
        midi = events_to_midi([])
        assert midi[:4] == b"MThd"
        assert b"MTrk" in midi

    def test_single_note_produces_midi(self):
        midi = events_to_midi([_note()])
        assert midi[:4] == b"MThd"
        assert len(midi) > 20

    def test_format_0_single_track(self):
        midi = events_to_midi([_note()])
        # Bytes 8-9 = format (0), bytes 10-11 = num tracks (1)
        fmt = struct.unpack(">H", midi[8:10])[0]
        tracks = struct.unpack(">H", midi[10:12])[0]
        assert fmt == 0
        assert tracks == 1

    def test_ppq_matches(self):
        midi = events_to_midi([_note()])
        ppq = struct.unpack(">H", midi[12:14])[0]
        assert ppq == MIDI_PPQ

    def test_multiple_notes_larger_output(self):
        one = events_to_midi([_note()])
        three = events_to_midi([_note(), _note(pitch_hz=880.0), _note(pitch_hz=220.0)])
        assert len(three) > len(one)

    def test_contains_note_on_byte(self):
        midi = events_to_midi([_note(channel=0)])
        assert bytes([0x90]) in midi  # note-on channel 0

    def test_contains_note_off_byte(self):
        midi = events_to_midi([_note(channel=0)])
        assert bytes([0x80]) in midi  # note-off channel 0

    def test_waveform_cc_in_output(self):
        midi = events_to_midi([_note(waveform=Waveform.TRIANGLE)])
        # CC 70 (waveform) = 2 (triangle)
        assert bytes([0xB0, 70, 2]) in midi

    def test_volume_cc_in_output(self):
        midi = events_to_midi([_note(volume=0.5)])
        # CC 7 (volume) = 64
        assert bytes([0xB0, 7, 64]) in midi

    def test_end_of_track_marker(self):
        midi = events_to_midi([_note()])
        assert midi.endswith(b"\xff\x2f\x00")


# ---------------------------------------------------------------------------
# render_to_wav — missing binary
# ---------------------------------------------------------------------------

class TestRenderToWavMissingBinary:
    def test_raises_file_not_found_when_binary_missing(self, tmp_path):
        missing = tmp_path / "no-such-binary"
        events = [_note()]
        with pytest.raises(FileNotFoundError, match="chant-host binary not found"):
            render_to_wav(events, tmp_path / "out.wav", host_path=missing)

    def test_error_message_includes_path(self, tmp_path):
        missing = tmp_path / "chant-host"
        events = [_note()]
        with pytest.raises(FileNotFoundError) as exc_info:
            render_to_wav(events, tmp_path / "out.wav", host_path=missing)
        assert str(missing.resolve()) in str(exc_info.value)

    def test_no_subprocess_called_when_binary_missing(self, tmp_path):
        missing = tmp_path / "no-such-binary"
        with patch("subprocess.run") as mock_run:
            with pytest.raises(FileNotFoundError):
                render_to_wav([_note()], tmp_path / "out.wav", host_path=missing)
            mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# render_to_wav — subprocess integration
# ---------------------------------------------------------------------------

class TestRenderToWavSubprocess:
    def test_passes_midi_file_to_host(self, tmp_path):
        fake_host = tmp_path / "chant-host"
        fake_host.write_text("#!/bin/sh\nexit 0\n")
        fake_host.chmod(0o755)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            render_to_wav([_note()], tmp_path / "out.wav", host_path=fake_host)

            call_args = mock_run.call_args[0][0]
            assert call_args[0] == str(fake_host.resolve())
            assert call_args[1].endswith(".mid")
            assert "-o" in call_args
            assert "--sample-rate" in call_args

    def test_two_ch_flag_passed(self, tmp_path):
        fake_host = tmp_path / "chant-host"
        fake_host.write_text("#!/bin/sh\nexit 0\n")
        fake_host.chmod(0o755)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            render_to_wav([_note()], tmp_path / "out.wav", two_ch=True, host_path=fake_host)

            call_args = mock_run.call_args[0][0]
            assert "--2ch" in call_args

    def test_raises_runtime_error_on_nonzero_exit(self, tmp_path):
        fake_host = tmp_path / "chant-host"
        fake_host.write_text("#!/bin/sh\nexit 1\n")
        fake_host.chmod(0o755)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {
                "returncode": 1, "stdout": "", "stderr": "boom"
            })()
            with pytest.raises(RuntimeError, match="chant-host failed"):
                render_to_wav([_note()], tmp_path / "out.wav", host_path=fake_host)
