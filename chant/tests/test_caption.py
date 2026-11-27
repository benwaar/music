"""Tests for caption generation."""

from chant.caption import caption, _hz_to_note_name, _tempo_description
from chant.schema import ChipType, NoteEvent, NoteTable, TrackMetadata, Waveform


def _table(
    source_format: str = "sid",
    title: str = "Test",
    author: str = "Author",
    chip: ChipType | None = ChipType.MOS6581,
    channels: int = 3,
    sub_songs: int = 1,
    extra: dict | None = None,
) -> NoteTable:
    return NoteTable(
        metadata=TrackMetadata(
            source_format=source_format,
            source_path="test.sid",
            title=title,
            author=author,
            chip=chip,
            channels=channels,
            sub_songs=sub_songs,
            extra=extra or {},
        )
    )


def test_basic_sid_caption():
    t = _table(
        title="The Shuffle",
        author="Zack Maxis",
        chip=ChipType.MOS8580,
        channels=6,
        extra={"released": "2026 Hokuto Force"},
    )
    c = caption(t)
    assert "MOS8580" in c
    assert "6-channel" in c
    assert '"The Shuffle"' in c
    assert "Zack Maxis" in c
    assert "2026 Hokuto Force" in c


def test_ay_caption():
    t = _table(
        source_format="ay",
        title="spring",
        author="SirIl",
        chip=ChipType.AY3_8910,
        channels=3,
        extra={"misc": "chaos construction 999"},
    )
    c = caption(t)
    assert "AY-3-8910" in c
    assert "spring" in c
    assert "chaos construction" in c


def test_xm_caption_with_bpm():
    t = _table(
        source_format="xm",
        title="Cool Track",
        author="",
        chip=ChipType.XM,
        channels=10,
        extra={"bpm": 125, "num_instruments": 15, "tracker": "FastTracker"},
    )
    c = caption(t)
    assert "125 BPM" in c
    assert "15 instruments" in c
    assert "10-channel" in c


def test_mod_caption_with_instruments():
    t = _table(
        source_format="mod",
        title="Test Mod",
        author="",
        chip=ChipType.MOD,
        channels=4,
        extra={"instruments": ["bass drum", "snare", "hihat", "lead"], "magic": "M.K."},
    )
    c = caption(t)
    assert "bass drum" in c
    assert "4-channel" in c


def test_mod_filters_liner_notes():
    t = _table(
        source_format="mod",
        chip=ChipType.MOD,
        channels=4,
        extra={"instruments": ["[greetings to all]", "bass", "this is a long instrument name that should be filtered out"], "magic": "M.K."},
    )
    c = caption(t)
    assert "greetings" not in c
    assert "bass" in c


def test_vgm_caption_with_game():
    t = _table(
        source_format="vgm",
        title="Azure Lake",
        author="",
        chip=ChipType.SN76489,
        channels=4,
        extra={"gd3": {"game_en": "Sonic 3", "system_en": "Sega Master System"}, "is_compressed": False},
    )
    c = caption(t)
    assert "Sonic 3" in c
    assert "Sega Master System" in c


def test_multi_subsong():
    t = _table(sub_songs=5)
    c = caption(t)
    assert "5 sub-songs" in c


def test_single_subsong_omitted():
    t = _table(sub_songs=1)
    c = caption(t)
    assert "sub-song" not in c


def test_no_chip():
    t = _table(chip=None)
    c = caption(t)
    assert "SID format" in c


def test_deterministic():
    t = _table(title="Repeat", author="Same")
    assert caption(t) == caption(t)


# --- Musical content caption tests ---


def _table_with_events(
    events: list[NoteEvent],
    source_format: str = "mod",
    bpm: int = 0,
    **kwargs,
) -> NoteTable:
    extra = kwargs.pop("extra", {})
    if bpm:
        extra["bpm"] = bpm
    return NoteTable(
        metadata=TrackMetadata(
            source_format=source_format,
            source_path="test.mod",
            title="Test",
            chip=ChipType.MOD,
            channels=4,
            extra=extra,
            **kwargs,
        ),
        events=events,
    )


def test_caption_includes_pitch_range():
    events = [
        NoteEvent(pitch_hz=261.6, channel=0, duration_ms=120),
        NoteEvent(pitch_hz=880.0, channel=1, duration_ms=120),
    ]
    c = caption(_table_with_events(events))
    assert "pitch range C4-A5" in c


def test_caption_includes_note_count():
    events = [NoteEvent(pitch_hz=440.0, channel=0, duration_ms=100) for _ in range(50)]
    c = caption(_table_with_events(events))
    assert "50 notes" in c


def test_caption_includes_tempo():
    events = [NoteEvent(pitch_hz=440.0, channel=0, duration_ms=100)]
    c = caption(_table_with_events(events, bpm=140))
    assert "upbeat tempo (140 BPM)" in c


def test_caption_includes_active_channels():
    events = [
        NoteEvent(pitch_hz=440.0, channel=0, duration_ms=100),
        NoteEvent(pitch_hz=440.0, channel=0, duration_ms=100),
        NoteEvent(pitch_hz=440.0, channel=0, duration_ms=100),
        NoteEvent(pitch_hz=440.0, channel=1, duration_ms=100),
        NoteEvent(pitch_hz=440.0, channel=2, duration_ms=100),
    ]
    c = caption(_table_with_events(events))
    assert "3 active channels" in c
    assert "lead on ch0" in c


def test_caption_no_events_no_musical_content():
    t = _table(source_format="sid")
    c = caption(t)
    assert "notes" not in c
    assert "pitch range" not in c


def test_hz_to_note_name_a4():
    assert _hz_to_note_name(440.0) == "A4"


def test_hz_to_note_name_middle_c():
    assert _hz_to_note_name(261.6) == "C4"


def test_tempo_descriptions():
    assert _tempo_description(60) == "slow"
    assert _tempo_description(100) == "moderate"
    assert _tempo_description(140) == "upbeat"
    assert _tempo_description(200) == "fast"
