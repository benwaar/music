"""Tests for the note table schema."""

from chant.schema import (
    ChipType,
    NoteEvent,
    NoteTable,
    TrackMetadata,
    Waveform,
)


def test_note_event_defaults():
    e = NoteEvent(pitch_hz=440.0)
    assert e.pitch_hz == 440.0
    assert e.duration_ms == 0.0
    assert e.channel == 0
    assert e.waveform is None
    assert e.effects == []


def test_note_event_full():
    e = NoteEvent(
        pitch_hz=261.63,
        duration_ms=125.0,
        channel=1,
        waveform=Waveform.PULSE,
        duty_cycle=0.5,
        volume=0.8,
        effects=["vibrato"],
    )
    assert e.waveform == Waveform.PULSE
    assert e.effects == ["vibrato"]


def test_track_metadata():
    m = TrackMetadata(
        source_format="sid",
        source_path="hvsc/test.sid",
        title="Test Song",
        author="Test Author",
        chip=ChipType.MOS6581,
        channels=3,
        sub_songs=2,
    )
    assert m.chip == ChipType.MOS6581
    assert m.sub_songs == 2


def test_note_table_empty():
    t = NoteTable(
        metadata=TrackMetadata(source_format="sid", source_path="x.sid")
    )
    assert t.duration_ms == 0.0
    assert t.pitch_range == (0.0, 0.0)
    assert t.events == []


def test_note_table_computed_properties():
    t = NoteTable(
        metadata=TrackMetadata(source_format="sid", source_path="x.sid"),
        events=[
            NoteEvent(pitch_hz=220.0, duration_ms=100.0),
            NoteEvent(pitch_hz=440.0, duration_ms=200.0),
            NoteEvent(pitch_hz=880.0, duration_ms=150.0),
        ],
    )
    assert t.duration_ms == 450.0
    assert t.pitch_range == (220.0, 880.0)


def test_waveform_values():
    assert Waveform.PULSE.value == "pulse"
    assert Waveform.NOISE.value == "noise"


def test_chip_type_values():
    assert ChipType.MOS6581.value == "MOS6581"
    assert ChipType.AY3_8910.value == "AY-3-8910"
