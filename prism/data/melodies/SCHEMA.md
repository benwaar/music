# Melody JSON Schema

Two example files in this directory show the format. Training data will be generated at scale when ML work begins.

## Structure

```json
{
  "title": "Melancholy Wistful",
  "tempo": 80,
  "analysis": {
    "mood": "melancholy, wistful, nostalgic",
    "style": "minor key, reflective",
    "energy": "calm and restrained",
    "movement": "descending with pauses",
    "character": "thoughtful",
    "imagery": "water, mist",
    "rhythm": "legato"
  },
  "notes": [
    { "note": "A4", "beats": 1.0 },
    { "note": "G4", "beats": 1.0 },
    { "note": "Rest", "beats": 0.5 }
  ]
}
```

## Fields

- **title** — human-readable name
- **tempo** — BPM (80–160 in existing data)
- **analysis** — semantic labels across up to 7 dimensions:
  - mood: cheerful, calm, melancholy, mysterious
  - style: genre/key description
  - energy: restrained, frantic, building, fading
  - movement: ascending, descending, wandering, arching
  - character: playful, timid, elegant, aggressive
  - imagery: fire, water, organic, mechanical
  - rhythm: legato, bouncy, syncopated, repetitive
- **notes** — array of `{ note, beats }` objects
  - note: pitch name with octave (C4, F#4, Bb5) or "Rest"
  - beats: float duration (1.0 = one beat)
  - Range: C3–B6 (MIDI 48–83)
