# Principles

## Voice

Write for someone who builds backend systems in C or TypeScript and wants to understand ML — not an ML audience. Avoid jargon without explanation. Analogies to systems programming are welcome.

## Audience

- Primary: developers with systems programming experience, no ML background
- Secondary: ML practitioners curious about audio generation or LoRA fine-tuning

## Non-negotiables

1. **Reproducibility.** Every dependency is in a file. `bash setup.sh && python -m pytest` works on a fresh clone.
2. **No committed data.** Scripts fetch everything. `_data/` is a symlink to drift's archive.
3. **Docs are part of done.** Code without explanation teaches nobody. Every milestone has an explainer.
4. **Small steps, frequent commits.** One concept per commit. Easy to bisect, easy to review.
5. **Hear it.** Audio is the ground truth. If you can't render a note table through beepers and listen, the step isn't complete.
6. **Sequences are structured data.** Note tables and financial event series are the same shape — ordered records with timing, magnitude, and type. Every design choice should work for both domains.
7. **Train on CPU first.** LoRA adapters must be small enough to train a few epochs on a laptop. GPU is optional acceleration, not a requirement.
8. **Local models.** Use ollama for inference during development. No cloud API dependencies for the core workflow.
