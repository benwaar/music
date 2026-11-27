"""Musical coherence metrics for chant-generated note sequences.

Goes beyond structural validity to measure musical quality:
  - pitch_entropy        — variety of pitches used
  - rhythm_regularity    — consistency of note durations
  - channel_balance      — evenness of event spread across channels
  - repetition_score     — fraction of consecutive identical events
"""

from __future__ import annotations

import math
from collections import Counter
from typing import List

from chant.schema import NoteEvent


def _pitch_to_midi(pitch_hz: float) -> int:
    """Convert frequency in Hz to nearest MIDI note number."""
    return round(69 + 12 * math.log2(pitch_hz / 440.0))


def pitch_entropy(events: List[NoteEvent]) -> float:
    """Shannon entropy (bits) of the pitch distribution.

    Higher = more varied pitches. 0.0 = all same note or empty list.
    Uses MIDI note numbers (rounded from pitch_hz).
    """
    if not events:
        return 0.0

    counts = Counter(_pitch_to_midi(e.pitch_hz) for e in events)
    total = len(events)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def rhythm_regularity(events: List[NoteEvent]) -> float:
    """Coefficient of variation (std_dev / mean) of note durations.

    Lower = more regular rhythm. 0.0 = all same duration or fewer than 2 events.
    """
    if len(events) < 2:
        return 0.0

    durations = [e.duration_ms for e in events]
    mean = sum(durations) / len(durations)
    if mean == 0.0:
        return 0.0

    variance = sum((d - mean) ** 2 for d in durations) / len(durations)
    std_dev = math.sqrt(variance)
    return std_dev / mean


def channel_balance(events: List[NoteEvent]) -> float:
    """Normalised entropy of event distribution across channels.

    1.0 = perfectly balanced, 0.0 = all on one channel or empty.
    """
    if not events:
        return 0.0

    counts = Counter(e.channel for e in events)
    num_channels = len(counts)
    if num_channels < 2:
        return 0.0

    total = len(events)
    raw_entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
    return raw_entropy / math.log2(num_channels)


def repetition_score(events: List[NoteEvent]) -> float:
    """Fraction of consecutive event pairs that are identical.

    Identical = same pitch_hz, duration_ms, channel, volume.
    1.0 = every consecutive pair identical. 0.0 = no repeats.
    Returns 0.0 for fewer than 2 events.
    """
    if len(events) < 2:
        return 0.0

    def _key(e: NoteEvent) -> tuple:
        return (e.pitch_hz, e.duration_ms, e.channel, e.volume)

    pairs = len(events) - 1
    matching = sum(1 for a, b in zip(events, events[1:]) if _key(a) == _key(b))
    return matching / pairs


def compute_all_metrics(events: List[NoteEvent]) -> dict[str, float]:
    """Compute all four musical coherence metrics at once.

    Returns a dict with keys:
      pitch_entropy, rhythm_regularity, channel_balance, repetition_score
    """
    return {
        "pitch_entropy": pitch_entropy(events),
        "rhythm_regularity": rhythm_regularity(events),
        "channel_balance": channel_balance(events),
        "repetition_score": repetition_score(events),
    }
