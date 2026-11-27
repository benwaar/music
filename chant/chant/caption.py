"""Generate text captions from NoteTable metadata.

Captions are the text half of the (text, note table) training pair.
They describe the track using available metadata: chip, channels,
format-specific details (instruments, BPM, game name).

Captions are deterministic — same input always produces the same output.
"""

from __future__ import annotations

import math
from collections import Counter

from chant.schema import ChipType, NoteTable


_CHIP_DESCRIPTIONS: dict[ChipType, str] = {
    ChipType.MOS6581: "Commodore 64 SID (MOS6581)",
    ChipType.MOS8580: "Commodore 64 SID (MOS8580)",
    ChipType.AY3_8910: "ZX Spectrum AY-3-8910",
    ChipType.SN76489: "Sega SN76489 PSG",
    ChipType.YM2612: "Sega Genesis YM2612 FM",
    ChipType.MOD: "Amiga ProTracker module",
    ChipType.XM: "FastTracker XM module",
}


def _filter_instrument_names(instruments: list[str]) -> list[str]:
    """Keep only names that look like real instrument labels.

    MOD instrument fields are heavily abused for liner notes, greetings,
    and ASCII art. Real instrument names tend to start with ST- prefixes,
    or be short lowercase words like 'bass', 'snare', 'hihat'.
    """
    result = []
    for name in instruments:
        if len(name) > 20 or len(name) < 2:
            continue
        if any(c in name for c in "[]{}()/\\!@#$&*"):
            continue
        if "  " in name:
            continue
        if name.isdigit():
            continue
        # ST-XX: prefix is a standard sample library naming convention
        if name.startswith("ST-") or name.startswith("st-"):
            result.append(name)
            continue
        # Skip anything that reads like prose (3+ spaces or 4+ words)
        words = name.split()
        if len(words) >= 4:
            continue
        result.append(name)
    return result


_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _hz_to_note_name(hz: float) -> str:
    """Convert frequency to nearest note name (e.g. 'C4', 'A#3')."""
    if hz <= 0:
        return "?"
    semitones_from_a4 = 12 * math.log2(hz / 440.0)
    midi_note = round(69 + semitones_from_a4)
    octave = (midi_note // 12) - 1
    name = _NOTE_NAMES[midi_note % 12]
    return f"{name}{octave}"


def _tempo_description(bpm: int) -> str:
    """Human-readable tempo label."""
    if bpm < 80:
        return "slow"
    if bpm < 120:
        return "moderate"
    if bpm < 160:
        return "upbeat"
    return "fast"


def _musical_content_parts(table: NoteTable) -> list[str]:
    """Describe musical content from note events."""
    if not table.events:
        return []

    parts: list[str] = []
    pitches = [e.pitch_hz for e in table.events if e.pitch_hz > 0]
    if pitches:
        lo, hi = min(pitches), max(pitches)
        parts.append(f"pitch range {_hz_to_note_name(lo)}-{_hz_to_note_name(hi)}")

    parts.append(f"{len(table.events)} notes")

    bpm = table.metadata.extra.get("bpm", 0)
    if bpm:
        parts.append(f"{_tempo_description(bpm)} tempo ({bpm} BPM)")

    channel_counts = Counter(e.channel for e in table.events)
    if channel_counts:
        dominant_ch = channel_counts.most_common(1)[0][0]
        total_channels = len(channel_counts)
        if total_channels > 1:
            parts.append(f"{total_channels} active channels, lead on ch{dominant_ch}")

    return parts


def caption(table: NoteTable) -> str:
    """Generate a text caption from a NoteTable's metadata."""
    m = table.metadata
    parts: list[str] = []

    # Chip / format
    if m.chip:
        parts.append(_CHIP_DESCRIPTIONS.get(m.chip, m.chip.value))
    else:
        parts.append(f"{m.source_format.upper()} format")

    # Channels
    if m.channels > 0:
        parts.append(f"{m.channels}-channel")

    # Title
    if m.title:
        parts.append(f'"{m.title}"')

    # Author
    if m.author:
        parts.append(f"by {m.author}")

    # Format-specific details
    if m.source_format == "xm":
        bpm = m.extra.get("bpm")
        num_inst = m.extra.get("num_instruments")
        if bpm:
            parts.append(f"{bpm} BPM")
        if num_inst:
            parts.append(f"{num_inst} instruments")

    if m.source_format == "mod":
        instruments = m.extra.get("instruments", [])
        real_instruments = _filter_instrument_names(instruments)
        if real_instruments:
            sample = real_instruments[:4]
            parts.append(f"instruments: {', '.join(sample)}")

    if m.source_format == "vgm":
        gd3 = m.extra.get("gd3", {})
        game = gd3.get("game_en")
        system = gd3.get("system_en")
        if game:
            parts.append(f"from {game}")
        if system:
            parts.append(f"on {system}")

    if m.source_format == "ay":
        misc = m.extra.get("misc", "")
        if misc:
            parts.append(f"({misc})")

    if m.source_format == "sid":
        released = m.extra.get("released", "")
        if released:
            parts.append(f"released {released}")

    # Sub-songs
    if m.sub_songs > 1:
        parts.append(f"{m.sub_songs} sub-songs")

    # Musical content from note events
    parts.extend(_musical_content_parts(table))

    return ", ".join(parts)
