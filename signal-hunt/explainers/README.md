# Signal Hunt — Explainers

Signal Hunt's audio-domain explainers live here. Cross-project ML concepts remain in the
[Games AI Lab Learning Hub](https://github.com/benwaar/games/tree/main/explainers) so future
Games AI Lab projects can reuse them.

## Audio Processing & Data

→ [Reading Waveforms & Spectrograms](reading-plots.md) — annotated audio examples and pipeline debugging
→ [Mel-Spectrograms](mel-spectrograms.md) — STFT, Mel scale, log-dB, and tensor conversion
→ [Signal-to-Noise Ratio](snr.md) — measuring noise and applying robust audio augmentation
→ [Data Collection](data-collection.md) — recording and extending the Signal Hunt dataset
→ [Batch Processing](batch-processing.md) — audio augmentation, manifest, and reproducible tensor generation

## Shared ML Concepts

→ [CNN Architecture](https://github.com/benwaar/games/blob/main/explainers/cnn-architecture.md) — CNN building blocks, illustrated with Signal Hunt
→ [Transfer Learning](https://github.com/benwaar/games/blob/main/explainers/transfer-learning.md) — frozen features and fine-tuning, with Signal Hunt results
→ [Training Loop](https://github.com/benwaar/games/blob/main/explainers/training-loop.md) — loss, backpropagation, Adam, scheduling, and early stopping
→ [Evaluation](https://github.com/benwaar/games/blob/main/explainers/evaluation.md) — precision, recall, F1, confusion matrices, and loss curves
→ [Train / Val / Test Split](https://github.com/benwaar/games/blob/main/explainers/train-val-test-split.md) — held-out evaluation and stratified splits
→ [Dataset & DataLoader](https://github.com/benwaar/games/blob/main/explainers/dataset-dataloader.md) — PyTorch dataset and batching concepts
→ [Libraries](https://github.com/benwaar/games/blob/main/explainers/libraries.md) — NumPy, PyTorch, and the project's dependencies
→ [Python Concepts](https://github.com/benwaar/games/blob/main/explainers/python-concepts.md) — Python patterns used in ML projects

---

## Signal Hunt — Project-specific explainers

### Iowa Piano Data (Phase 3 — M13)

Why the University of Iowa dataset, what domain gap means, why we switched from NSynth.

→ [Iowa piano data](iowa-piano-data.md)

---

### Phase 3 Evaluation — Per-Note Results (Phase 3 — M16)

89.5% test accuracy on 12 chromatic notes. F4 hardest (semitone adjacency). Mel resolution analysis.

→ [Phase 3 evaluation](evaluation-phase3.md)

---

### Chord Synthesis — Mixing Notes in the Time Domain (Phase 4 — M18)

Mixing Iowa WAVs into chord clips. Clipping prevention, dynamic combinations, spectrogram comparison.

→ [Chord synthesis](chord-synthesis.md)

---

### The Two-Model Feedback Design (Phase 4 — M19)

Name model (verdict) + note-set model (correction). Same clip, two passes. Mirrors real teaching.

→ [Two-model feedback](two-model-feedback.md)

---

### Multi-Label Evaluation (Phase 4 — M20)

Exact-match vs per-label F1, threshold selection, why precision and recall behave differently when multiple labels are simultaneously active. Phase 4 results: D4/F4 weakest (appear in only 2 chords), precision high across all notes (false negatives, not false positives).

→ [Multi-label evaluation](multi-label-evaluation.md)

---

### RNNs and the CNN→RNN Reshape (Phase 4 — M21)

How GRUs work, why bidirectional matters, and the `(B,64,16,T) → mean → permute → GRU` reshape that connects the CNN to the RNN. The Signal Hunt progression classifier: 36 time steps, 73,956 params, 66.7% on 4 progression classes.

→ [RNN sequence modelling](rnn-sequence-modelling.md)

---

### Chord Progressions as Sequence Modelling (Phase 4 — M22)

Why order matters (I-IV-V-I ≠ V-IV-I-I), how synthetic progressions give free labels, the gap between 66.7% on 16 clips and what more data would do, and how progression classification connects to the piano teacher goal.

→ [Chord progressions](chord-progressions.md)

---

### Browser Inference Pipeline (Phase 5)

How the trained CNN runs entirely in the browser via `onnxruntime-web` (WASM). ONNX export, inlining weights for browser delivery, replicating the Python Mel spectrogram pipeline in JavaScript, and the gotchas (Slaney scale, `top_db=80`, external data files).

→ [Browser inference pipeline](browser-pipeline.md)

---

### Real-Time Sliding Window Inference (Phase 5)

How the demo classifies audio continuously — the ring buffer, the ScriptProcessor callback loop, why predictions feel instant, and the tradeoffs of window size. Connects to keyword spotting and wake-word detection in production.

→ [Real-time inference](realtime-inference.md)
