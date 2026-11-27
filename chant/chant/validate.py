"""Structural validation for chant-generated note sequences.

Checks that a list of NoteEvent objects (or a raw token string) meets
the structural constraints required for valid chip-tune output:

  - Non-empty sequence
  - Pitches within human hearing range (20 Hz – 20,000 Hz)
  - Durations positive and ≤ 30,000 ms
  - Channel indices within chip-tune hardware limit (0–31)
  - Not all events identical (the model must generate variety)

Also provides a comparison helper for conditioned vs unconditioned
generation metrics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from chant.schema import NoteEvent
from chant import tokeniser

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PITCH_MIN_HZ: float = 20.0        # lower bound of human hearing range
PITCH_MAX_HZ: float = 20_000.0    # upper bound of human hearing range
DURATION_MAX_MS: float = 30_000.0 # 30-second hard cap
CHANNEL_MAX: int = 31              # chip-tune hardware limit
DURATION_QUANT_MS: int = 10        # quantisation step for diversity comparison


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Outcome of a structural validation run."""

    valid: bool
    num_events: int
    issues: list[str] = field(default_factory=list)

    # Ranges — None when no events are present
    pitch_range: Optional[tuple[float, float]] = None
    duration_range: Optional[tuple[float, float]] = None

    # Per-check booleans (True = check passed)
    channels_used: set[int] = field(default_factory=set)
    pitch_in_range: bool = True
    duration_in_range: bool = True
    channels_in_range: bool = True
    has_variety: bool = True


# ---------------------------------------------------------------------------
# Core validator
# ---------------------------------------------------------------------------

def validate_events(events: List[NoteEvent]) -> ValidationResult:
    """Validate a list of NoteEvent objects structurally.

    Returns a ValidationResult.  valid=True only if no issues were found.
    All issues are collected before returning (no early exit).
    """
    issues: list[str] = []

    # --- empty check --------------------------------------------------------
    if not events:
        return ValidationResult(
            valid=False,
            num_events=0,
            issues=["sequence is empty"],
        )

    # --- pitch range --------------------------------------------------------
    pitches = [e.pitch_hz for e in events]
    min_pitch = min(pitches)
    max_pitch = max(pitches)
    pitch_in_range = True

    if min_pitch < PITCH_MIN_HZ:
        pitch_in_range = False
        issues.append(
            f"pitch {min_pitch:.2f} Hz is below minimum {PITCH_MIN_HZ} Hz"
        )
    if max_pitch > PITCH_MAX_HZ:
        pitch_in_range = False
        issues.append(
            f"pitch {max_pitch:.2f} Hz exceeds maximum {PITCH_MAX_HZ} Hz"
        )

    # --- duration range -----------------------------------------------------
    durations = [e.duration_ms for e in events]
    min_dur = min(durations)
    max_dur = max(durations)
    duration_in_range = True

    if min_dur <= 0:
        duration_in_range = False
        issues.append(
            f"duration {min_dur:.2f} ms must be > 0"
        )
    if max_dur > DURATION_MAX_MS:
        duration_in_range = False
        issues.append(
            f"duration {max_dur:.2f} ms exceeds maximum {DURATION_MAX_MS} ms"
        )

    # --- channel range ------------------------------------------------------
    channels = {e.channel for e in events}
    channels_in_range = True
    bad_channels = [c for c in channels if c < 0 or c > CHANNEL_MAX]
    if bad_channels:
        channels_in_range = False
        for c in sorted(bad_channels):
            issues.append(
                f"channel {c} is outside allowed range 0–{CHANNEL_MAX}"
            )

    # --- variety check ------------------------------------------------------
    # Events are identical when pitch, duration, channel, and volume all match.
    def _event_key(e: NoteEvent) -> tuple:
        return (e.pitch_hz, e.duration_ms, e.channel, e.volume)

    has_variety = len({_event_key(e) for e in events}) > 1
    if not has_variety:
        issues.append("all events are identical — no variety in generated sequence")

    return ValidationResult(
        valid=len(issues) == 0,
        num_events=len(events),
        issues=issues,
        pitch_range=(min_pitch, max_pitch),
        duration_range=(min_dur, max_dur),
        channels_used=channels,
        pitch_in_range=pitch_in_range,
        duration_in_range=duration_in_range,
        channels_in_range=channels_in_range,
        has_variety=has_variety,
    )


# ---------------------------------------------------------------------------
# Token-string entry point
# ---------------------------------------------------------------------------

def validate_token_string(text: str) -> ValidationResult:
    """Decode a raw token string and validate the resulting events.

    If decode raises or returns an empty list the result is immediately
    invalid with issue 'unparseable token string'.
    """
    try:
        events = tokeniser.decode(text)
    except Exception:
        return ValidationResult(
            valid=False,
            num_events=0,
            issues=["unparseable token string"],
        )

    if not events:
        return ValidationResult(
            valid=False,
            num_events=0,
            issues=["unparseable token string"],
        )

    return validate_events(events)


# ---------------------------------------------------------------------------
# Conditioned vs unconditioned comparison
# ---------------------------------------------------------------------------

def _pitch_to_semitone(pitch_hz: float) -> int:
    """Round a frequency to the nearest MIDI semitone index."""
    if pitch_hz <= 0:
        return 0
    return round(69 + 12 * math.log2(pitch_hz / 440.0))


def _quantise_duration(duration_ms: float) -> int:
    """Quantise duration to nearest DURATION_QUANT_MS bucket."""
    return round(duration_ms / DURATION_QUANT_MS) * DURATION_QUANT_MS


def compare_conditioned_vs_unconditioned(
    conditioned: List[NoteEvent],
    unconditioned: List[NoteEvent],
) -> dict:
    """Return diversity metrics for two generation runs.

    Useful for measuring whether text conditioning actually influences
    the output compared with unconditioned (prompt-free) generation.

    Keys returned:
      pitch_diversity_conditioned      — unique MIDI semitones in conditioned
      pitch_diversity_unconditioned    — unique MIDI semitones in unconditioned
      duration_diversity_conditioned   — unique quantised durations (10 ms buckets)
      duration_diversity_unconditioned — same for unconditioned
      channel_spread_conditioned       — unique channels in conditioned
      channel_spread_unconditioned     — unique channels in unconditioned
    """
    def _pitch_diversity(events: List[NoteEvent]) -> int:
        return len({_pitch_to_semitone(e.pitch_hz) for e in events})

    def _duration_diversity(events: List[NoteEvent]) -> int:
        return len({_quantise_duration(e.duration_ms) for e in events})

    def _channel_spread(events: List[NoteEvent]) -> int:
        return len({e.channel for e in events})

    return {
        "pitch_diversity_conditioned": _pitch_diversity(conditioned),
        "pitch_diversity_unconditioned": _pitch_diversity(unconditioned),
        "duration_diversity_conditioned": _duration_diversity(conditioned),
        "duration_diversity_unconditioned": _duration_diversity(unconditioned),
        "channel_spread_conditioned": _channel_spread(conditioned),
        "channel_spread_unconditioned": _channel_spread(unconditioned),
    }
