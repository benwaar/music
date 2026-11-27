# The Idea Behind Drift

## Where it started

This project grew from two separate interests converging.

### How machines see

Tom White's *Synthetic Abstractions* series (drib.net) explores the gap between human and machine perception. He creates abstract images — just shapes and colours to a human eye — that neural networks confidently classify as "electric guitar" or "forklift." The work asks: what does a machine *actually* look at when it recognises an object? The answer is structure we can't see — patterns in pixel distributions, frequency relationships, spatial correlations that are invisible to us but dominant to a trained model.

This raised a question: if machines see structure in images that humans can't, what happens when you reverse the process? Instead of asking "what does the machine see in this image?" — ask "what can the machine *make* from this image?"

### Natural Noise — the art project

The Natural Noise project (in `art-natural-noise/`) started from a simpler observation: real-world photographs have hidden structure. A photograph of foliage isn't random pixels — it has frequency patterns, colour distributions, spatial correlations. Pass it through a transfer function (sigmoid, posterize, wave), apply banding, and that hidden structure becomes visible as abstract art.

The creative discovery was that the *transfer function* is the interesting parameter, not the image. The same photograph with steepness 4 produces something interesting; steepness 10 produces rubbish. The art is in the parameter space — the iteration loop of tweak, look, tweak again.

### The leap to audio

Mel-spectrograms are greyscale images. A 128×176 spectrogram is just a 2D array — the same data shape as a photograph. Low values are silence/bass, high values are treble/energy.

If a photograph has hidden structure that makes interesting visual art, does the same photograph have hidden structure that makes interesting audio? Can you treat a photo as a spectrogram and denoise it into a chip-tune?

The answer turned out to be yes. A photograph of foliage and a photograph of dried grass, fed through the same diffusion model at the same strength, produce audibly different chip-tune samples. The dark central band of a tree trunk becomes a quiet gap; the bright scattered leaves become high-frequency energy. The image's structure steers the sound.

## What makes drift different

**Spectrogram art** (Aphex Twin hiding his face in a track, tools like SpectroTrace) works backwards — engineering audio so the spectrogram looks like a picture. It's steganography. The image is the *goal*, not the input.

**AI music generators** (Tunee, Musely, Google's Noise2Music) are text-prompted: describe what you want, get music back. The creative input is language.

**Drift uses visual and environmental structure as creative input.** A photograph doesn't become the sound — it *nudges* the generation. The diffusion model interprets the image's structure through what it learned about chip-tune spectrograms. Different images produce different nudges. Different transfer functions (linear, sigmoid, wave) reshape the image before it becomes a spectrogram seed, giving another axis of creative control — the same lesson from the art project.

The cross-feed loop is the end goal: photograph → Natural Noise art → drift seed → chip-tune → Mel-spectrogram → back into Natural Noise. Two domains, one creative process, the same hidden structure flowing between them.

## The creative process

The Natural Noise art project taught a key lesson: **the value is in the iteration loop, not the algorithm.** Same image + same function, but different parameters produce wildly different output. The creative act is tweaking knobs and curating results.

Drift inherits this. The interesting output isn't a single generation — it's a batch of 20 samples at different strengths and transfer functions, listened to, sorted, and curated. The model is a creative tool, not a replacement for taste.

## Prior art and influences

- **Tom White** — *Synthetic Abstractions* series (drib.net). Abstract images that machines classify as objects. The perception gap between human and machine vision.
- **Aphex Twin** — "∆Mᵢ⁻¹=−α ∑Dᵢ[n] [∑j [...]]" (1999, *Windowlicker* EP). His face hidden in the spectrogram. Pioneer of the spectrogram-as-canvas idea.
- **Venetian Snares** — *Songs About My Cats* (2001). Cat photos encoded in spectrograms.
- **Google Research** — *Noise2Music* (2023). Diffusion on spectrograms conditioned on text prompts.
- **SpectroTrace, Img2Sound** — Tools for encoding images into audio via direct pixel-to-frequency mapping.

None of these use images or field recordings as a *diffusion seed* — where the input structure steers generation rather than being literally encoded. That's the novel part.
