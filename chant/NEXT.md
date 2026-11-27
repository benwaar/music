# Next — M4: Playback and demo

M3 complete — 92.4% quality gate, MIDI pipeline working, 4/5 val examples render to playable WAV.

## M4 plan

End-to-end demo: text prompt → note table → chant-host → chip-tune audio.

### Steps

- [ ] CLI demo script — `python -m chant.demo "A fast SID bass line"` does generate + render + play (opens system audio player)
- [ ] Batch demo — render 10 diverse prompts, save WAVs + a manifest JSON with prompt/metrics/path
- [ ] Demo page — static HTML that lists prompts, embeds WAV players, shows note table visualisation
- [ ] Archive readiness — verify cold-clone workflow, update setup.sh

### Archive readiness (before moving to music repo)

- [x] Bundle LoRA adapter (6.5MB) — committed to `models/lora_adapter/`, gitignore exception for safetensors
- [ ] Verify cold-clone: `git clone → bash setup.sh → python -m chant.generate "prompt"` works
- [ ] Fix utala (games repo) retraining at the same time — test all three projects cold-clone → run
