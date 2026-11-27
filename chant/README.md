# Chant — Text-to-Chiptune via LoRA Fine-Tuning

Describe a chip-tune in words, generate note tables that beepers can play. Fine-tune a model with LoRA to produce structured musical sequences from text descriptions.

## Why this exists

Chiptune is a genre with hard rules — limited channels, specific waveforms, fixed frequency ranges. Think of it like pixel art: a constrained style with clear conventions.

A LoRA adapter teaches a general-purpose AI model to work within a specific domain. The same way an image LoRA teaches a model "draw in manga style," a chiptune LoRA teaches a model "compose in 8-bit style with these constraints." You describe what you want in plain English, the model produces structured output that follows the rules of the genre.

This is the same technique used to adapt foundation models to any specialised domain — legal documents, medical imaging, financial data. The skill is domain-agnostic. Chiptune is just a domain where you can hear when the model gets it wrong.

### Audio → Finance

Note tables and financial event sequences are structurally identical: ordered sequences of structured records with timing, magnitude, and type fields.

| Audio | Finance |
|-------|---------|
| "rising arpeggio, pulse wave, C major" → note table | "volatile open, mean reversion midday, gap close" → event series |
| Note = (pitch, duration, waveform, duty, effects) | Event = (price, volume, instrument, direction, volatility) |
| Text-conditioned generation of musical sequences | Text-conditioned generation of market scenarios |
| Signal Hunt classifier verifies rendered output | Statistical tests verify distribution match |
| LoRA adapts model to chip-tune domain | LoRA adapts model to specific asset class |

The fine-tuning workflow is the same: curate domain data, attach LoRA adapters, train with conditioning, evaluate against ground truth. Learn it once on audio (where you can hear mistakes), apply it to structured data.

## Dependencies

| Project | What it provides |
|---------|-----------------|
| Drift | Spectrogram dataset, diffusion training patterns |
| Signal Hunt | Audio classifier — eval judge to verify rendered output |
| Beepers | Note table format + VSTi playback engine — renders generated sequences as audio |
