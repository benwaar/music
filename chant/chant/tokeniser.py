"""Token encoder for chant note sequences.

Converts a NoteTable's events into a flat token string an LLM can learn to generate.

## Token format

Each NoteEvent becomes a group of four tokens, separated from adjacent events by ' | '.
The sequence is wrapped in <BOS> and <EOS> boundary tokens.

    <BOS> N{midi} D{ms} C{n} V{level} | N{midi} D{ms} C{n} V{level} <EOS>

Field tokens:

| Token     | Meaning                                     | Range          |
|-----------|---------------------------------------------|----------------|
| N{midi}   | MIDI note number (pitch)                    | N0 – N127      |
| D{ms}     | Duration quantised to nearest 10 ms         | D10 – D5000    |
| C{n}      | Channel index                               | C0 – C31       |
| V{level}  | Volume quantised to 8 levels (0 = silent)   | V0 – V7        |
| |         | Event separator                             | —              |
| <BOS>     | Sequence start                              | —              |
| <EOS>     | Sequence end                                | —              |

## Pitch conversion

    midi = round(69 + 12 * log2(pitch_hz / 440))   then clamped to [0, 127]

## Reversibility

The format is fully reversible:
- Split on whitespace to get tokens.
- Strip <BOS>/<EOS>.
- Split on ' | ' to separate events.
- Each event is exactly four tokens in order: N, D, C, V.
- Parse each by its leading letter and convert back:
    hz  = 440 * 2 ** ((midi - 69) / 12)
    ms  = int(D_token[1:])              (quantised, not exact original)
    ch  = int(C_token[1:])
    vol = int(V_token[1:]) / 7.0        (quantised)

Agent 2 implements the decoder using this spec.
"""

import math
from typing import List

from chant.schema import NoteEvent, NoteTable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIDI_MIN: int = 0
MIDI_MAX: int = 127
DURATION_QUANT_MS: int = 10          # quantisation step in milliseconds
VOLUME_LEVELS: int = 8               # 0-7 inclusive

_DURATION_MIN: int = DURATION_QUANT_MS
_DURATION_MAX: int = 5000            # maximum represented duration token

_CHANNEL_MAX: int = 31               # C0–C31


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pitch_to_midi(pitch_hz: float) -> int:
    """Convert frequency in Hz to a MIDI note number, clamped to [0, 127]."""
    midi = round(69 + 12 * math.log2(pitch_hz / 440.0))
    return max(MIDI_MIN, min(MIDI_MAX, midi))


def _quantise_duration(duration_ms: float) -> int:
    """Round duration to the nearest 10 ms, minimum 10 ms."""
    quantised = round(duration_ms / DURATION_QUANT_MS) * DURATION_QUANT_MS
    return max(_DURATION_MIN, quantised)


def _quantise_volume(volume: float | None) -> int:
    """Map 0.0–1.0 volume to 0–7. None → 7 (full volume)."""
    if volume is None:
        return VOLUME_LEVELS - 1  # 7 = full
    clamped = max(0.0, min(1.0, volume))
    return round(clamped * (VOLUME_LEVELS - 1))


def _encode_event(event: NoteEvent) -> str:
    """Return the four-token string for a single NoteEvent."""
    midi = _pitch_to_midi(event.pitch_hz)
    dur = _quantise_duration(event.duration_ms)
    ch = max(0, min(_CHANNEL_MAX, event.channel))
    vol = _quantise_volume(event.volume)
    return f"N{midi} D{dur} C{ch} V{vol}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def encode(table: NoteTable) -> str:
    """Convert a NoteTable to a token string.

    Events with pitch_hz <= 0 are skipped (they represent rests or silence).
    Returns '<BOS> <EOS>' for a table with no valid events.
    """
    parts: List[str] = []
    for event in table.events:
        if event.pitch_hz <= 0:
            continue
        parts.append(_encode_event(event))

    inner = " | ".join(parts)
    if inner:
        return f"<BOS> {inner} <EOS>"
    return "<BOS> <EOS>"


def decode(text: str) -> List[NoteEvent]:
    """Parse a token string back into a list of NoteEvent objects.

    - Strips <BOS> and <EOS> boundary tokens.
    - Splits on '|' to recover individual events.
    - Each event must have exactly four tokens in order: N, D, C, V.
    - Malformed events are silently skipped.
    - Returns an empty list for empty / whitespace-only input.

    Decoded values are quantised (lossy):
      - pitch_hz = 440 * 2 ** ((midi - 69) / 12)
      - duration_ms as stored in the D token (already a 10 ms multiple)
      - volume = level / 7.0
      - waveform is always None (not encoded)
    """
    if not text or not text.strip():
        return []

    tokens = text.split()

    # Remove boundary tokens wherever they appear in the token list
    tokens = [t for t in tokens if t not in ("<BOS>", "<EOS>")]

    # Rejoin and re-split on '|' separator
    rejoined = " ".join(tokens)
    event_chunks = rejoined.split("|")

    events: List[NoteEvent] = []
    for chunk in event_chunks:
        event_tokens = chunk.split()
        if len(event_tokens) != 4:
            continue  # skip malformed events
        n_tok, d_tok, c_tok, v_tok = event_tokens
        try:
            if not (n_tok.startswith("N") and d_tok.startswith("D")
                    and c_tok.startswith("C") and v_tok.startswith("V")):
                continue
            midi = int(n_tok[1:])
            dur = float(d_tok[1:])
            ch = int(c_tok[1:])
            level = int(v_tok[1:])
        except ValueError:
            continue

        pitch_hz = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        volume = level / (VOLUME_LEVELS - 1)  # level / 7.0

        events.append(NoteEvent(
            pitch_hz=pitch_hz,
            duration_ms=dur,
            channel=ch,
            volume=volume,
            waveform=None,
        ))

    return events


def vocabulary() -> List[str]:
    """Return the full token vocabulary, sorted.

    Includes every token that encode() can emit:
      - <BOS>, <EOS>
      - |
      - N0 … N127
      - D10, D20, … D5000  (500 tokens)
      - C0 … C31
      - V0 … V7

    Total: 2 + 1 + 128 + 500 + 32 + 8 = 671 tokens.
    """
    tokens: List[str] = ["<BOS>", "<EOS>", "|"]

    tokens += [f"N{i}" for i in range(MIDI_MIN, MIDI_MAX + 1)]

    dur_steps = range(_DURATION_MIN, _DURATION_MAX + 1, DURATION_QUANT_MS)
    tokens += [f"D{d}" for d in dur_steps]

    tokens += [f"C{i}" for i in range(_CHANNEL_MAX + 1)]

    tokens += [f"V{i}" for i in range(VOLUME_LEVELS)]

    return sorted(tokens)
