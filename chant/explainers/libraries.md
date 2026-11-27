# Libraries Reference

Libraries used across the chant project, with the specific functions that matter.

Audience: developers with C or TypeScript backgrounds. Python imports work like `#include` / `import` — each module is a namespace.

---

## torch

PyTorch — tensor math, autograd, and optimisers. Used in `train.py`.

| Symbol | What it does |
|--------|-------------|
| `torch.float32` | dtype constant — tells `from_pretrained` to load weights as 32-bit floats (required for CPU training; bfloat16 is GPU-only) |
| `torch.tensor(0.0)` | Creates a scalar tensor on the default device. Used as an accumulator for batch loss. |
| `tensor.clone()` | Returns a copy of a tensor that shares no memory with the original. Used to copy `input_ids` into `labels` before masking. |
| `tensor.backward()` | Runs backprop from this tensor through the whole computation graph (autograd). Equivalent to computing all gradients. |
| `tensor.item()` | Extracts a Python `float` from a scalar tensor — used to log loss values. |
| `(tensor != -100).sum()` | Element-wise comparison + reduction; checks whether any completion tokens survive after prompt masking. |
| `torch.optim.AdamW(params, lr=...)` | AdamW optimiser — `params` is an iterator over all trainable tensors, `lr` is learning rate. `.zero_grad()`, `.step()` are the standard optimiser loop calls. |
| `model.parameters()` | Iterator over all tensors in the model. Used for optimiser initialisation and for counting trainable params (`p.requires_grad`). |
| `model.train()` | Puts the model in training mode (enables dropout, batch norm updates). Contrast with `model.eval()`. |
| `p.numel()` | Returns the number of elements in a tensor — used to sum total/trainable parameter counts. |

---

## transformers

Hugging Face Transformers — model loading and tokenisation. Used in `train.py`.

| Symbol | What it does |
|--------|-------------|
| `AutoModelForCausalLM.from_pretrained(name, dtype=...)` | Downloads/caches a causal language model by its Hub ID (e.g. `HuggingFaceTB/SmolLM2-360M`) and returns it as a `torch.nn.Module`. `dtype` controls weight precision. |
| `AutoTokenizer.from_pretrained(name)` | Downloads/caches the matching tokeniser — handles vocabulary, BPE merges, special tokens. |
| `tokenizer(text, truncation=True, max_length=N, return_tensors="pt")` | Calling the tokeniser encodes text to a dict of PyTorch tensors: `input_ids` (token IDs) and `attention_mask` (1 = real token, 0 = padding). |
| `tokenizer.pad_token` / `tokenizer.eos_token` | Special token attributes — SmolLM2 has no pad token by default, so the code sets it to the EOS token to avoid crashes during batching. |
| `encoded["input_ids"].shape[1]` | Shape of a 2-D tensor `[batch, seq_len]` — `.shape[1]` gives the sequence length, used to find where the prompt ends and the completion begins. |
| `model(input_ids=..., attention_mask=..., labels=...)` | Forward pass. When `labels` are supplied the model computes cross-entropy loss internally. The return value has a `.loss` attribute. |
| `model.save_pretrained(path)` / `tokenizer.save_pretrained(path)` | Saves weights + config (or vocab + merges) to a directory. Standard checkpoint format; reloadable with `from_pretrained`. |

---

## peft

Parameter-Efficient Fine-Tuning library — LoRA adapters. Used in `train.py`.

| Symbol | What it does |
|--------|-------------|
| `TaskType.CAUSAL_LM` | Enum value that tells PEFT the model is a causal language model (decoder-only), so it knows which layers are eligible adapter targets. |
| `LoraConfig(task_type, r, lora_alpha, lora_dropout, target_modules)` | Dataclass that specifies the adapter. `r` is the rank (bottleneck dimension — lower = fewer params). `lora_alpha` is a scale factor (commonly set to `2*r`). `target_modules` names which weight matrices to inject adapters into — here `q_proj` and `v_proj` (query and value projections in self-attention). |
| `get_peft_model(model, lora_config)` | Wraps a base model with the adapters described by `lora_config`. Freezes all original parameters (`requires_grad=False`) and inserts trainable low-rank matrices. Returns a `PeftModel` with the same forward interface. |
| `PeftModel` | The wrapped model type. Not imported directly in this codebase — it is the return type of `get_peft_model`. After training, `model.save_pretrained` saves only the adapter weights (a few MB), not the full base model. |

---

## datasets

Hugging Face Datasets — in-memory dataset containers. Used in `build_training.py`.

| Symbol | What it does |
|--------|-------------|
| `Dataset.from_list(records)` | Creates an in-memory columnar dataset from a list of dicts. Each key becomes a column. Analogous to building a typed table from a list of structs. |
| `DatasetDict(splits)` | Dict-like container that holds multiple named `Dataset` objects — typically `"train"` and `"validation"`. Used by Hugging Face `Trainer` and by downstream tooling. |
| `ds.save_to_disk(path)` | Serialises the dataset to Apache Arrow format on disk. Faster to reload than re-parsing JSONL, and memory-mappable. |

---

## numpy

Not used in this project. No parsers import numpy.

---

## Standard library

### dataclasses (`schema.py`, `train.py`)

| Symbol | What it does |
|--------|-------------|
| `@dataclass` | Class decorator — auto-generates `__init__`, `__repr__`, `__eq__` from annotated fields. Like a typed struct. |
| `field(default_factory=list)` | Used for mutable default values. Without this, all instances would share one list — a classic Python footgun. |
| `asdict(instance)` | Recursively converts a dataclass to a plain `dict`. Used in `build_dataset.py` to serialise records to JSON. |

### enum (`schema.py`)

| Symbol | What it does |
|--------|-------------|
| `Enum` | Base class for enumerations. `Waveform` and `ChipType` extend it. Each member has a `.value` (the string) and a name. `Waveform("pulse")` constructs from value; `Waveform.PULSE.value` gives `"pulse"`. |

### math (`tokeniser.py`, `caption.py`)

| Symbol | What it does |
|--------|-------------|
| `math.log2(x)` | Base-2 logarithm. Used in the pitch-to-MIDI conversion: `midi = round(69 + 12 * log2(hz / 440))`. The same formula appears in MIDI spec. |

### json

| Symbol | What it does |
|--------|-------------|
| `json.loads(line)` | Parses a JSON string to a Python dict/list. Used to read JSONL line-by-line. |
| `json.dumps(obj, ensure_ascii=False)` | Serialises to a JSON string. `ensure_ascii=False` preserves Unicode characters in titles/author names rather than escaping them as `\uXXXX`. |
| `json.dump(obj, f)` | Serialises directly to a file object. Used to write `loss_history.json`. |

### pathlib

| Symbol | What it does |
|--------|-------------|
| `Path(string)` | Constructs a path object. Prefer over raw strings — handles separators cross-platform. |
| `path / "subdir"` | Operator overload — joins path segments. Equivalent to `os.path.join`. |
| `path.exists()` | Returns `True` if the path exists on disk. |
| `path.mkdir(parents=True, exist_ok=True)` | Creates the directory and any missing parents. `exist_ok=True` is a no-op if it already exists (no error). |
| `path.rglob("*.sid")` | Recursive glob — yields all matching paths under a directory tree. Used in `build_dataset.py` to discover files. |

### argparse

| Symbol | What it does |
|--------|-------------|
| `ArgumentParser(description=...)` | Creates a CLI argument parser. |
| `parser.add_argument("--flag", type=T, default=V)` | Declares a named flag with an automatic type conversion and fallback default. |
| `parser.parse_args()` | Reads `sys.argv`, validates, and returns a namespace object (attribute access: `args.epochs`). |

### collections (`caption.py`)

| Symbol | What it does |
|--------|-------------|
| `Counter(iterable)` | Counts occurrences — returns a dict-like `{value: count}`. Used to find the most active channel: `channel_counts.most_common(1)[0][0]`. |

### random (`build_dataset.py`)

| Symbol | What it does |
|--------|-------------|
| `random.Random(seed)` | Creates a seeded random instance (not global state). Reproducible shuffles — same seed → same train/val split every run. |
| `rng.shuffle(list)` | In-place Fisher-Yates shuffle. |

---

## Rust crates (synth/chant-host)

### eno-state-zx 0.1.2 (`synth/src/main.rs`)

Published crate — 1-bit ZX Spectrum beeper synth engines. Used as a library, not as a plugin.

| Symbol | What it does |
|--------|-------------|
| `ToneEngine::render_note_table(&[(u8,u8)], sample_rate)` | Renders a 1ch note table (duration, period pairs) to a Vec of f32 samples. Duration = 256-toggle groups, period = Z80 counter value (1-255). |
| `Tone2chEngine::render_note_table(&[(u8,u8,u8)], sample_rate)` | Renders a 2ch interleave note table (duration, ch1_period, ch2_period). Two independent period counters sharing one speaker bit. |
| `ToneEngine::freq_for_period(period)` | Converts a Z80 period value to frequency in Hz. Used to verify the inverse mapping (Hz → period). |
| `wav::write_wav(path, samples, sample_rate)` | Writes f32 samples as 16-bit mono WAV. |

**Coming from C:** These are the exact algorithms from the Z80 beeper — integer countdown loops, T-state budgets, speaker bit toggles. The Rust code simulates the CPU cycle-by-cycle.

**Coming from TypeScript:** Think of `render_note_table` as a pure function: note data in, audio samples out. No side effects, no state between calls.

### midly 0.5 (`synth/src/main.rs`)

Zero-copy MIDI parser. Reads Standard MIDI Files into typed event streams.

| Symbol | What it does |
|--------|-------------|
| `Smf::parse(bytes)` | Parses a MIDI file from a byte slice. Returns header + track list. |
| `TrackEventKind::Midi { channel, message }` | A channel voice message — note on/off, control change, etc. |
| `MidiMessage::NoteOn { key, vel }` | Note-on event with MIDI note number (0-127) and velocity. Velocity 0 = note-off convention. |
| `Timing::Metrical(tpb)` | Ticks per beat from the MIDI header — needed to convert delta ticks to milliseconds. |
