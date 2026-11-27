"""Tests for chant.tokeniser — encode, decode, vocabulary, and round-trips."""

import math
from pathlib import Path

import pytest

from chant.schema import NoteEvent, NoteTable, TrackMetadata
from chant.tokeniser import decode, encode, vocabulary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEMITONE = 2 ** (1 / 12)       # frequency ratio for one semitone
_PITCH_TOL = _SEMITONE           # ±1 semitone
_DUR_TOL = 5.0                   # ±5 ms (half a 10 ms quantisation step)
_VOL_TOL = 1 / 7.0               # ±1 volume level

def _make_table(*events: NoteEvent) -> NoteTable:
    meta = TrackMetadata(source_format="test", source_path="test.mod")
    return NoteTable(metadata=meta, events=list(events))


def _note(pitch_hz: float, dur: float = 100.0, ch: int = 0,
          vol: float | None = 0.5) -> NoteEvent:
    return NoteEvent(pitch_hz=pitch_hz, duration_ms=dur, channel=ch, volume=vol)


# ---------------------------------------------------------------------------
# Encode — unit tests
# ---------------------------------------------------------------------------

def test_encode_single_event():
    table = _make_table(_note(440.0, 100.0, 0, 1.0))
    result = encode(table)
    assert result.startswith("<BOS>")
    assert result.endswith("<EOS>")
    assert "N69" in result   # 440 Hz = MIDI 69
    assert "D100" in result
    assert "C0" in result
    assert "V7" in result    # 1.0 → level 7


def test_encode_multiple_events():
    table = _make_table(_note(440.0), _note(494.0))
    result = encode(table)
    assert result.count("|") == 1   # one separator between two events


def test_encode_empty():
    table = _make_table()
    assert encode(table) == "<BOS> <EOS>"


def test_encode_skips_zero_pitch():
    table = _make_table(_note(0.0, 100.0), _note(440.0, 100.0))
    result = encode(table)
    # Only one real event — no separator expected
    assert "|" not in result
    assert "N69" in result


def test_encode_clamps_midi():
    very_high = _note(50_000.0)   # above N127
    very_low = _note(0.001)       # effectively below N0 (but > 0 so not skipped)
    table_high = _make_table(very_high)
    table_low = _make_table(very_low)
    assert "N127" in encode(table_high)
    assert "N0" in encode(table_low)


def test_encode_quantises_duration():
    table = _make_table(
        _note(440.0, 123.0),   # → D120
        _note(440.0, 7.0),     # → D10 (minimum)
    )
    result = encode(table)
    assert "D120" in result
    assert "D10" in result


def test_encode_none_volume():
    table = _make_table(NoteEvent(pitch_hz=440.0, duration_ms=100.0, volume=None))
    result = encode(table)
    assert "V7" in result    # None → full volume


# ---------------------------------------------------------------------------
# Decode — unit tests
# ---------------------------------------------------------------------------

def test_decode_single_event():
    text = "<BOS> N69 D100 C0 V7 <EOS>"
    events = decode(text)
    assert len(events) == 1
    e = events[0]
    assert math.isclose(e.pitch_hz, 440.0, rel_tol=1e-6)
    assert e.duration_ms == 100.0
    assert e.channel == 0
    assert math.isclose(e.volume, 1.0, rel_tol=1e-6)
    assert e.waveform is None


def test_decode_empty_string():
    assert decode("") == []
    assert decode("   ") == []


def test_decode_strips_bos_eos():
    # Tokens present but no events between them
    assert decode("<BOS> <EOS>") == []


def test_decode_skips_malformed():
    # Missing V token, extra token, wrong prefix order
    text = (
        "<BOS> "
        "N69 D100 C0 "            # missing V → skip
        "| N69 D100 C0 V7 "       # valid
        "| X99 D100 C0 V3 "       # wrong prefix → skip
        "| N69 D100 C0 V7 EXTRA " # too many tokens → skip
        "<EOS>"
    )
    events = decode(text)
    assert len(events) == 1


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

def test_vocabulary_size():
    vocab = vocabulary()
    # 2 boundary + 1 sep + 128 N + 500 D + 32 C + 8 V = 671
    assert 600 <= len(vocab) <= 700


def test_vocabulary_contains_expected():
    vocab = set(vocabulary())
    assert "<BOS>" in vocab
    assert "<EOS>" in vocab
    assert "|" in vocab
    assert "N0" in vocab
    assert "N127" in vocab
    assert "D10" in vocab
    assert "D5000" in vocab
    assert "C0" in vocab
    assert "C31" in vocab
    assert "V0" in vocab
    assert "V7" in vocab


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------

def test_round_trip_single_note():
    original = _note(440.0, 200.0, 2, 0.5)
    table = _make_table(original)
    decoded = decode(encode(table))
    assert len(decoded) == 1
    d = decoded[0]

    assert d.pitch_hz / original.pitch_hz < _PITCH_TOL
    assert original.pitch_hz / d.pitch_hz < _PITCH_TOL
    assert abs(d.duration_ms - original.duration_ms) <= _DUR_TOL
    assert d.channel == original.channel
    assert abs(d.volume - original.volume) <= _VOL_TOL


def test_round_trip_multi_channel():
    events = [_note(440.0, 100.0, ch, 0.5) for ch in range(4)]
    table = _make_table(*events)
    decoded = decode(encode(table))
    assert len(decoded) == 4
    channels = {e.channel for e in decoded}
    assert channels == {0, 1, 2, 3}


def test_round_trip_extreme_values():
    cases = [
        _note(4186.0, 10.0, 0, 1.0),    # ~C8, very high pitch
        _note(27.5, 5000.0, 0, 0.0),     # ~A0, very low pitch, long dur, zero vol
    ]
    table = _make_table(*cases)
    decoded = decode(encode(table))
    assert len(decoded) == 2

    for orig, dec in zip(cases, decoded):
        assert dec.pitch_hz / orig.pitch_hz < _PITCH_TOL
        assert orig.pitch_hz / dec.pitch_hz < _PITCH_TOL
        assert abs(dec.duration_ms - orig.duration_ms) <= _DUR_TOL + orig.duration_ms * 0.01


def test_round_trip_real_data():
    """Encode/decode a real MOD file and verify quantisation tolerances."""
    mod_path = Path("_data/modarchive/mod/qasteron.mod")
    if not mod_path.exists():
        pytest.skip("Real data not available (_data symlink missing)")

    from chant.parsers.mod import parse_mod
    table = parse_mod(mod_path)

    # Only keep events that encode() will keep (pitch > 0)
    orig_events = [e for e in table.events if e.pitch_hz > 0]
    if not orig_events:
        pytest.skip("No pitched events in test file")

    decoded = decode(encode(table))

    assert len(decoded) == len(orig_events), (
        f"Event count mismatch: {len(orig_events)} encoded, {len(decoded)} decoded"
    )

    for i, (orig, dec) in enumerate(zip(orig_events, decoded)):
        ratio = dec.pitch_hz / orig.pitch_hz
        assert 1 / _PITCH_TOL <= ratio <= _PITCH_TOL, (
            f"Event {i}: pitch {orig.pitch_hz:.1f} Hz → decoded {dec.pitch_hz:.1f} Hz"
        )

        assert abs(dec.duration_ms - orig.duration_ms) <= _DUR_TOL + 5, (
            f"Event {i}: duration {orig.duration_ms} ms → decoded {dec.duration_ms} ms"
        )

        assert dec.channel == orig.channel, (
            f"Event {i}: channel {orig.channel} → decoded {dec.channel}"
        )
