
## Plan

### M1 — Dataset: text-to-note-table pairs

- Extract note tables from drift's chip-tune archive (MIDI, VGM, tracker formats → structured sequences)
- Pair with text captions: instrument, waveform, pitch pattern, rhythm, effects
- Output format matches beepers' tracker: (pitch, duration, waveform, duty cycle, effects) per row
- Validation split with held-out descriptions
- Quality gate: captions are precise enough that a human could reconstruct the sequence

### M2 — LoRA adapter for text-conditioned sequence generation

- Base model: SmolLM2-360M (causal LM, 362M params, trained on code + text)
- Custom 671-token vocabulary for note events (pitch, duration, channel, volume)
- LoRA adapters on attention layers (rank 8, 819K trainable params — 0.23% of total)
- Training format: caption prompt → note token sequence completion
- CPU-only training — feasible because LoRA keeps the trainable surface tiny
- Quality gate: generated note tables are valid (parseable, in-range values, musically coherent)

### M3 — Evaluation pipeline

- Render generated note tables through beepers VSTi → audio
- Signal Hunt classifier scores rendered output against prompt intent
- Structural metrics: valid note ranges, rhythm coherence, waveform accuracy
- A/B comparison: unconditioned vs text-conditioned generation
- Quality gate: conditioned output measurably closer to prompt than random generation

### M4 — Playback and demo

- End-to-end: text prompt → note table → beepers VSTi → chip-tune audio
- Demo page showing prompt → sequence → waveform → playback

## Archive readiness (before moving to music repo)

- [ ] **Bundle LoRA adapter (6.5MB).** The trained adapter (`_data/chant_checkpoints/lora_adapter/`) is gitignored. Small enough to commit directly or attach as a GitHub Release. Before archiving, pick one and ensure `setup.sh` restores it on a fresh clone.
- [ ] **Bundle or document base model dependency.** The LoRA adapter sits on top of `HuggingFaceTB/SmolLM2-360M` (~720MB, downloaded via `setup.sh`). Verify the HuggingFace download step works reliably for a cold clone.
- [ ] **Verify cold-clone workflow.** Fresh clone → `bash setup.sh` → `python -m chant.generate "prompt"` should work end to end.
- [ ] **Fix utala (games repo) at the same time.** Utala's inference works (TinyNN JSON committed) but retraining is broken (`/models/` gitignored, no download script). Add a script or commit the training artifacts when archiving drift+chant. Test all three projects cold-clone → run in one pass.

## Skills covered

| Skill | Detail |
|-------|--------|
| LoRA fine-tuning | Parameter-efficient adaptation of a pre-trained model |
| Custom tokenisation | Domain-specific vocabulary for structured sequences |
| Causal LM training | Prompt/completion pairs with label masking |
| Dataset curation | Building high-quality text-sequence pairs from existing data |
| Eval-driven training | Automated evaluation pipeline, not just loss curves |
| Multimodal | Text → structured sequence generation (same shape as text → event series) |

## Base model

**SmolLM2-360M** — chosen for CPU trainability and fast iteration. 362M parameters, Llama architecture, 8192 token context window, 49K BPE vocabulary. LoRA adapters bring the trainable surface down to 819K parameters (0.23%), making a full training run feasible on a laptop CPU in minutes.

## References

| Resource | What it covers |
|----------|---------------|
| [Llama-3.2-1B-Chiptune-MIDI](https://huggingface.co/omayib/Llama-3.2-1B-Chiptune-MIDI) | LoRA fine-tune of Llama 3.2 1B on chiptune MIDI. Closest prior art — same concept, no eval pipeline or playback loop. |
| [MIDI-LLM](https://arxiv.org/abs/2511.03942) | Extends Llama 3.2 1B with MIDI tokens for text-to-MIDI. Two-stage training recipe. ISMIR 2026 paper. |
| [Text2Music-InstrumentControl](https://github.com/sooyoung-ryu/Text2Music-InstrumentControl) | LoRA fine-tuning for instrument-level control in text-to-music generation. |
| [MusicGen LoRA](https://github.com/ylacombe/musicgen-dreamboothing) | Practical guide to fine-tuning MusicGen with LoRA. |
| [ACE-Step LoRA experiments](https://www.tavus.io/blog/learnings-from-random-lora-finetuning-experiments-on-a-guided-music-synthesis-diffusion-model) | What breaks when you LoRA a music diffusion model. Practical lessons on attention and text processing. |
