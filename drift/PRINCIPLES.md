# Principles

## Voice

Write for someone who builds backend systems in C or TypeScript and wants to understand ML — not an ML audience. Avoid jargon without explanation. Analogies to systems programming are welcome.

## Audience

- Primary: developers with systems programming experience, no ML background
- Secondary: ML practitioners curious about audio generation

## Non-negotiables

1. **Reproducibility.** Every dependency is in a file. `bash scripts/setup.sh && python -m pytest` works on a fresh clone.
2. **No committed data.** Scripts fetch everything. `_data/` and `_tools/` are gitignored.
3. **Docs are part of done.** Code without explanation teaches nobody. Every milestone has an explainer.
4. **Small steps, frequent commits.** One concept per commit. Easy to bisect, easy to review.
5. **Hear it.** Audio is the ground truth. If you can't listen to the output, the step isn't complete.
6. **Spectrograms are images.** The entire approach hinges on treating Mel-spectrograms as greyscale images. Every architectural choice should respect this — standard vision techniques, nothing audio-specific in the model.
7. **Train on CPU first.** The model must be small enough to train a few epochs on a laptop. GPU is optional acceleration, not a requirement.
