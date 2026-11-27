# LoRA Fine-Tuning in chant

How chant teaches SmolLM2-360M to generate chip-tune note sequences from text — without touching the base model.

---

## What LoRA is and why

Training a full neural network from scratch requires enormous compute. Fine-tuning one — adjusting a pre-trained model's weights for a new task — still requires updating hundreds of millions of parameters, which is expensive and risks destroying the general knowledge the model already has.

LoRA (Low-Rank Adaptation) sidesteps this. The core insight: **weight updates during fine-tuning tend to be low-rank** — most of the update's information lives in a small subspace. So instead of updating the full weight matrix `W` (shape `[d, d]`), LoRA adds two small matrices alongside it:

```
W' = W + B × A
```

Where `A` has shape `[r, d]` and `B` has shape `[d, r]`, with rank `r << d`. The base matrix `W` is frozen. Only `A` and `B` are trained. At the end, you can either keep them separate (what chant does) or merge them back into `W` for zero-overhead inference.

**Analogy for C developers.** Imagine a large shared library (`libc.so`) that you cannot recompile. LoRA is like writing a thin shim that intercepts specific function calls, applies a small transform, and passes the result through — without forking the original binary. The shim is tiny, deployable independently, and swappable per use case.

**Analogy for TypeScript developers.** Think of it as a `Proxy` wrapping a frozen object. The base object's methods are untouched. The proxy intercepts specific property reads and injects a learned delta. You can have multiple proxies (adapters) for the same base object, each trained on a different task.

> **In practice.** LoRA is the reason fine-tuning is accessible without a GPU cluster. A full fine-tune of a 360M model would require significant VRAM and hours on expensive hardware. The LoRA adapters chant trains are 3 MB and train on a laptop CPU overnight. The same technique (at larger rank) is how most LLM fine-tunes happen in production — hosted model providers let you upload a LoRA adapter, not a full model fork.

---

## How it works in chant

### The base model

ChipTune sequences are essentially structured text — fixed tokens in a known grammar. That makes them a natural fit for a small language model. Chant uses **SmolLM2-360M**:

- 362 million parameters
- Llama architecture (transformer decoder, causal attention)
- 8192 token context window
- 49,152 BPE vocabulary

It's small enough to load into RAM and train on CPU in reasonable time. It already understands token sequences and positional relationships — which is exactly what note table generation needs.

### LoRA config

From `TrainConfig` in `chant/train.py`:

```python
lora_rank: int = 8
lora_alpha: int = 16
lora_dropout: float = 0.05
target_modules: list[str] = field(
    default_factory=lambda: ["q_proj", "v_proj"]
)
```

- **Rank 8** — the `r` in `B × A`. Controls adapter capacity. Rank 8 is a common default for domain adaptation tasks.
- **Alpha 16** — a scaling factor. The effective learning rate for the adapter is `(alpha / rank) × lr`. Here `16/8 = 2.0`, doubling the adapter's update magnitude relative to raw learning rate. This is a standard heuristic.
- **Target modules** — `q_proj` and `v_proj` are the query and value projection matrices inside each attention layer. These are where the model learns which parts of the sequence to attend to. They're the highest-leverage targets for task adaptation.

The `attach_lora` function wires this up:

```python
def attach_lora(model, config: TrainConfig):
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=config.target_modules,
    )
    peft_model = get_peft_model(model, lora_config)
    return peft_model
```

`get_peft_model` wraps the model: it freezes all base weights, injects the `A` and `B` matrices alongside each targeted projection, and returns an object with the same forward-pass interface. The rest of the training code doesn't need to know the difference.

### Trainable parameter count

```
print_trainable_params(model)
# Trainable: 819,200 / 362,000,000 (0.23%)
```

819,200 trainable parameters out of 362 million. The base model is completely frozen — gradients never reach it.

**Coming from C.** This is similar to only relinking the `.o` files that changed, not recompiling the entire translation unit. The linker (here: the optimizer) only touches the symbols it needs to update.

**Coming from TS.** This is the difference between patching a dependency in `node_modules` versus forking and publishing your own version. LoRA is the patch approach — surgical, composable, and easy to discard.

### Why CPU training is feasible here

Three factors make this work without a GPU:

1. **Small adapter.** Only 819K parameters receive gradient updates. The base model participates in the forward pass but its gradients are never computed or stored.
2. **Small rank.** The intermediate matrix dimension is 8. Multiply operations stay small.
3. **Batch size 1.** No parallelism needed. Each step processes one example at a time.

Throughput is roughly **1.2 seconds per step** with 512-token sequences. Slower than a GPU, but not impractical for a research project running overnight.

---

## The training format

Causal language models learn by predicting the next token given all previous tokens. To teach a task (text → note sequence), the prompt describes the task and the completion is the target output. The model learns to continue the prompt with valid completions.

### Prompt/completion structure

```
### Instruction:
{caption}
### Response:
<BOS> N60 D120 C0 V7 | N62 D60 C0 V6 | ... <EOS>
```

The `### Instruction:` / `### Response:` markers are conventional fine-tuning separators. They're just tokens — the model learns that text after `### Response:` is where it should produce note sequences.

### Label masking

The key detail: **loss is only computed on the completion tokens, not the prompt**.

From `tokenize_example` in `chant/train.py`:

```python
input_ids = encoded["input_ids"]
labels = input_ids.clone()
labels[0, :prompt_len] = -100
```

`-100` is a convention in PyTorch's cross-entropy loss: it means "ignore this position". The model still sees the prompt tokens as context (they're in `input_ids`), but no gradient is generated from them. The loss only backpropagates through the note sequence tokens.

**Coming from C.** Think of it as `readonly` input versus writable output in a function signature. The prompt tokens are `const` — read during the forward pass, never differentiated.

**Coming from TS.** It's like writing a type assertion that says "these positions are `never` for the purposes of loss computation." The shape of the tensor is unchanged, but those positions are masked out of the error signal.

### Truncation

```python
max_tokens: int = 2048
```

Sequences are truncated at 2048 BPE tokens. For note sequences, that works out to roughly:
- ~850 note tokens (each note is a few BPE subwords)
- ~170 note events (`N D C V` groups)

Longer sequences are truncated tail-first. If the truncation eats all completion tokens, the example is discarded:

```python
if (labels != -100).sum() == 0:
    return None
```

---

## The training loop

Each training step:

1. **Forward pass.** The model predicts next-token probabilities at every position. The loss function (cross-entropy) compares predictions against the ground-truth tokens — but only where `labels != -100`, i.e. the completion.

2. **Backward pass.** PyTorch computes gradients via automatic differentiation. Because base weights are frozen (`requires_grad=False`), gradients only flow through the LoRA `A` and `B` matrices in `q_proj` and `v_proj`.

3. **Optimizer step.** AdamW updates the adapter weights using the computed gradients.

From the training loop in `chant/train.py`:

```python
optimizer = torch.optim.AdamW(
    model.parameters(), lr=config.learning_rate
)

for batch in batched(examples, config.batch_size):
    optimizer.zero_grad()

    batch_loss = torch.tensor(0.0)
    for ex in batch:
        outputs = model(
            input_ids=ex["input_ids"],
            attention_mask=ex["attention_mask"],
            labels=ex["labels"],
        )
        batch_loss = batch_loss + outputs.loss

    batch_loss = batch_loss / len(batch)
    batch_loss.backward()
    optimizer.step()
```

**Coming from C.** `backward()` is automatic differentiation — the runtime computes `∂loss/∂w` for every trainable weight by walking the computation graph backwards. You don't write the gradient functions; PyTorch's autograd traces the forward pass and derives them.

**Coming from TS.** `model.parameters()` returns an iterable of tensors. The `AdamW` optimizer holds references to them (by pointer, not by value). `optimizer.step()` mutates them in place. `optimizer.zero_grad()` clears accumulated gradient state — equivalent to resetting an accumulator before the next event.

### What AdamW does

AdamW is a standard adaptive gradient optimizer. For each parameter `w`, it tracks:
- `m` — exponential moving average of gradients (momentum)
- `v` — exponential moving average of squared gradients (adaptive per-parameter learning rate)

The update is roughly: `w -= lr × m / (sqrt(v) + ε)`. AdamW adds weight decay (L2 regularisation) separately from the gradient — a small but important numerical difference from plain Adam that often improves generalisation.

---

## Checkpointing

After training, the adapter is saved separately from the base model:

```python
save_path = config.checkpoint_dir / "lora_adapter"
model.save_pretrained(str(save_path))
tokenizer.save_pretrained(str(save_path))
```

This saves only the adapter weights (`A` and `B` matrices for each targeted layer), not the base model. Sizes:

| Artifact | Size |
|---|---|
| SmolLM2-360M base | ~720 MB |
| LoRA adapter | ~3 MB |

To load and use the trained adapter:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained("HuggingFaceTB/SmolLM2-360M")
model = PeftModel.from_pretrained(base, "_data/chant_checkpoints/lora_adapter")
tokenizer = AutoTokenizer.from_pretrained("_data/chant_checkpoints/lora_adapter")
```

The base model is loaded once and shared. Multiple adapters (trained on different corpora or formats) can be swapped in and out without reloading the base.

**Coming from C.** This is `dlopen` for a 3 MB plugin. The base model is `libc`. The adapter is a small `.so` that overrides specific symbol behaviour.

**Coming from TS.** This is lazy-loading a module that wraps an existing singleton. The singleton (`base`) is never modified. The wrapper (`PeftModel`) intercepts the attention projections and injects the learned delta at inference time.

---

## Running it

```bash
# Full training run
python -m chant.train

# Quick smoke test (10 examples, 1 epoch)
python -m chant.train --max-examples 10 --epochs 1 --log-every 1
```

Expected output:

```
=== chant LoRA training ===
  Base model: HuggingFaceTB/SmolLM2-360M
  LoRA rank: 8, alpha: 16
  Target modules: ['q_proj', 'v_proj']
  Trainable: 819,200 / 362,000,000 (0.23%)

Loading training data...
  2149 raw examples
  2149 after tokenization (max 2048 tokens)

  epoch 1/3  step 10  loss 3.1402  avg 3.2847
  ...
  Saved adapter to _data/chant_checkpoints/lora_adapter/
```

Loss should decrease from ~3–4 at the start toward ~0.1 or lower after a full training run. If loss stays flat or increases, check that the dataset was built (`python -m chant.build_training`) and that examples contain completion tokens after truncation.

---

## Training results

Three epochs on 588 examples, CPU-only, max 2048 BPE tokens, ~35 minutes total:

| Epoch | Avg loss | Time  |
|-------|----------|-------|
| 1     | ~0.16    | ~12m  |
| 2     | ~0.08    | ~12m  |
| 3     | ~0.04    | ~12m  |

Final loss: **0.035**, best: **0.017**.

### Quality gate

Generated 10 sequences from held-out val captions:

- **10/10 parseable** — every output decoded to valid NoteEvents
- **10/10 pitch in range** — all pitches between 20 Hz and 20 kHz
- **10/10 duration in range** — all durations positive
- **8/10 channels in range** — two outputs had channel numbers > 31
- Most outputs: **42 events** (the truncation ceiling at 512 new tokens)

The model learned the `<BOS> N{midi} D{ms} C{n} V{level} | ... <EOS>` format reliably. The channel violations are minor — a clamp in the decoder would fix them.

### Crash resilience

Training saves the adapter and state after every epoch. If interrupted:

```bash
python -m chant.train --epochs 3 --max-tokens 2048 --resume
```

Picks up from the last completed epoch. Only the in-progress epoch is lost.
