"""Canonical note table schema for chant.

All parsers (SID, AY, MOD/XM, VGM) output these dataclasses.
Downstream code (caption generation, training) only sees this schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Waveform(Enum):
    """Chip-tune waveform types across all supported chips."""
    PULSE = "pulse"
    TRIANGLE = "triangle"
    SAWTOOTH = "sawtooth"
    NOISE = "noise"
    SQUARE = "square"
    FM = "fm"
    PCM = "pcm"


class ChipType(Enum):
    """Sound chips represented in the corpus."""
    MOS6581 = "MOS6581"
    MOS8580 = "MOS8580"
    AY3_8910 = "AY-3-8910"
    SN76489 = "SN76489"
    YM2612 = "YM2612"
    MOD = "MOD"
    XM = "XM"


@dataclass
class NoteEvent:
    """A single note in a sequence.

    Maps to one row in the output table. All fields are optional except
    pitch_hz — parsers fill what they can, caption generation works with
    whatever is present.
    """
    pitch_hz: float
    duration_ms: float = 0.0
    channel: int = 0
    waveform: Optional[Waveform] = None
    duty_cycle: Optional[float] = None
    volume: Optional[float] = None
    effects: list[str] = field(default_factory=list)


@dataclass
class TrackMetadata:
    """Per-file metadata common to all chip-tune formats."""
    source_format: str
    source_path: str
    title: str = ""
    author: str = ""
    chip: Optional[ChipType] = None
    channels: int = 0
    sub_songs: int = 1
    extra: dict = field(default_factory=dict)


@dataclass
class NoteTable:
    """A complete parsed track: metadata + ordered note events.

    This is the canonical output of every parser and the input to
    caption generation.
    """
    metadata: TrackMetadata
    events: list[NoteEvent] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if not self.events:
            return 0.0
        return sum(e.duration_ms for e in self.events)

    @property
    def pitch_range(self) -> tuple[float, float]:
        if not self.events:
            return (0.0, 0.0)
        pitches = [e.pitch_hz for e in self.events if e.pitch_hz > 0]
        if not pitches:
            return (0.0, 0.0)
        return (min(pitches), max(pitches))
