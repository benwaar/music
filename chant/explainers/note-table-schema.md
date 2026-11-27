# Note Table Schema

The note table is the canonical data structure in chant. Every parser (SID, AY, MOD/XM, VGM) outputs one. Caption generation and model training only see this schema — they never touch raw chip-tune files.

## Why a common schema?

Chip-tune formats are wildly different internally — SID files are 6502 machine code, VGM files are register write streams, MOD files are tracker patterns with embedded PCM. But the musical information maps to the same shape: an ordered list of note events with timing, pitch, and timbre.

By parsing each format into one canonical structure, everything downstream works the same regardless of source format.

## The three dataclasses

### `TrackMetadata`

Per-file info common to all formats:

| Field | Type | Description |
|-------|------|-------------|
| `source_format` | `str` | `"sid"`, `"ay"`, `"mod"`, `"xm"`, `"vgm"` |
| `source_path` | `str` | Relative path to the source file |
| `title` | `str` | Song title from the file header |
| `author` | `str` | Composer / author |
| `chip` | `ChipType?` | Sound chip (MOS6581, AY-3-8910, etc.) |
| `channels` | `int` | Number of audio channels |
| `sub_songs` | `int` | Number of sub-songs in the file (default 1) |
| `extra` | `dict` | Format-specific fields that don't fit the common schema |

### `NoteEvent`

One row in the note table — a single note:

| Field | Type | Description |
|-------|------|-------------|
| `pitch_hz` | `float` | Frequency in Hz (required) |
| `duration_ms` | `float` | Duration in milliseconds |
| `channel` | `int` | Which voice/channel (0-indexed) |
| `waveform` | `Waveform?` | pulse, triangle, sawtooth, noise, square, fm, pcm |
| `duty_cycle` | `float?` | Pulse width (0.0–1.0), only for pulse/square waves |
| `volume` | `float?` | Normalised volume (0.0–1.0) |
| `effects` | `list[str]` | Effect names: vibrato, portamento, arpeggio, etc. |

### `NoteTable`

A complete parsed track: metadata + events.

```python
table = NoteTable(
    metadata=TrackMetadata(
        source_format="sid",
        source_path="hvsc/The_Shuffle.sid",
        title="The Shuffle",
        author="Zack Maxis",
        chip=ChipType.MOS6581,
        channels=3,
    ),
    events=[
        NoteEvent(pitch_hz=261.63, duration_ms=125.0, channel=0, waveform=Waveform.PULSE),
        NoteEvent(pitch_hz=329.63, duration_ms=125.0, channel=0, waveform=Waveform.PULSE),
        # ...
    ],
)
```

Computed properties:
- `table.duration_ms` — total duration (sum of all events)
- `table.pitch_range` — `(min_hz, max_hz)` across all events

## Coming from C

This is a tagged union pattern. In C you'd have a `struct note_event` with fields and a `struct track` with a header + `note_event*` array. The Python dataclasses are the same — just with optional fields instead of sentinel values.

## Coming from JS/TS

Think of it as a TypeScript interface with optional properties. `NoteEvent` is `{ pitch_hz: number; duration_ms?: number; waveform?: Waveform; ... }`. The `NoteTable` is `{ metadata: TrackMetadata; events: NoteEvent[] }`.

## In practice

Note tables and financial event series are structurally identical. Replace `pitch_hz` with `price`, `waveform` with `instrument_type`, `effects` with `order_flags` — same schema, different domain. The parsing and captioning pipeline transfers directly.

## Design decisions

- **`pitch_hz` is the only required field on `NoteEvent`.** Some formats can't provide duration (SID is register-based, not event-based). Parsers fill what they can.
- **`extra` dict on metadata** captures format-specific fields (e.g. SID chip model flags, XM tracker name) without polluting the common schema.
- **Enums for waveforms and chips** — prevents typo bugs in caption generation. Parsers map format-specific values to enum members.
