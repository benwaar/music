# Python Concepts Reference

Patterns used in this project that are unfamiliar coming from C or TypeScript.
Each entry has a short "coming from C" and "coming from TS" callout.

---

## `@dataclass` and `field(default_factory=...)`

`@dataclass` auto-generates `__init__`, `__repr__`, and `__eq__` from your field annotations — you just describe the shape.

```python
# schema.py
@dataclass
class NoteEvent:
    pitch_hz: float
    effects: list[str] = field(default_factory=list)
```

The `field(default_factory=list)` is required for mutable defaults. If you wrote `effects: list[str] = []`, Python would share **one list object** across every instance — a classic mutable default trap.

**Coming from C:** Like a struct, but `__init__` is generated automatically. The mutable-default rule has no equivalent in C — it's a Python-specific gotcha because default values are evaluated once at class definition time, not per call.

**Coming from TS:** Like an interface + constructor rolled into one. TypeScript's `{}` default in a parameter is copied per call; Python's class-level `= []` is not — hence `default_factory`.

---

## `from __future__ import annotations`

```python
# train.py, schema.py, build_training.py
from __future__ import annotations
```

This makes all annotations in the file **lazy strings** — they are not evaluated at import time. Without it, a type like `list[str]` in a class body would fail on Python 3.8 because `list` wasn't yet subscriptable. It also lets you reference a class inside its own definition (forward references).

**Coming from C:** No direct equivalent. Think of it as telling the compiler "don't resolve type names yet — just store them as strings."

**Coming from TS:** TypeScript resolves types at compile time, so forward references just work. This import patches Python's runtime type evaluation to behave similarly.

---

## Gradient tracking: `.requires_grad` and `torch.no_grad()`

PyTorch tracks every operation on tensors that have `requires_grad=True`, building a computation graph so it can call `.backward()` to compute gradients automatically.

```python
# train.py
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
```

LoRA freezes the base model weights (`requires_grad=False`) and only trains the small adapter matrices. During inference, wrap code in `torch.no_grad()` to skip building that graph entirely — saves memory and time.

**Coming from C:** Analogous to reference counting, but for derivatives. Each tensor op appends a node to a DAG; `.backward()` walks it in reverse, accumulating gradients via the chain rule.

**Coming from TS:** No language-level analogy. Think of it as a reactive computation graph — like an observable chain, but for math rather than events.

---

## Context managers (`with` statement)

```python
# train.py, build_training.py
with open(jsonl_path) as f:
    for line in f:
        ...
```

The `with` block guarantees the file is closed when the block exits — even on exception. The object's `__enter__` runs on entry, `__exit__` on exit.

**Coming from C:** This is RAII. The file handle's destructor (cleanup) is deterministic and scoped — no need to `fclose()` manually.

**Coming from TS:** Like `try { ... } finally { f.close() }`, but the cleanup is attached to the object itself, not scattered at every call site. Identical in spirit to `using` in newer TS/C#.

---

## Generator functions and `yield`

```python
# train.py
def batched(examples: list, batch_size: int) -> Iterator[list]:
    for i in range(0, len(examples), batch_size):
        yield examples[i : i + batch_size]
```

A function that contains `yield` is a **generator**. Calling it returns a lazy iterator — it runs up to the first `yield`, pauses, and resumes on the next `next()` call. No list is built in memory; elements are produced one at a time.

**Coming from C:** Like a coroutine or a state machine that suspends at `yield` and resumes where it left off. The stack frame is preserved between calls.

**Coming from TS:** Identical to ES6 generator functions (`function*` / `yield`). Same semantics, different syntax.

---

## Union type syntax: `float | None`

```python
# tokeniser.py
def _quantise_volume(volume: float | None) -> int: ...

# train.py
max_examples: int | None = None
```

`float | None` means "either a float or None." This is Python 3.10+ syntax. On older Pythons you'd write `Optional[float]` from `typing`. With `from __future__ import annotations`, this syntax works even on 3.8/3.9 because annotations are stored as strings, not evaluated.

**Coming from C:** No direct equivalent — C has no optional types (you'd use a sentinel value or a pointer). Think of `None` as a typed null.

**Coming from TS:** Identical to `number | null` or `number | undefined`. Same intent, cleaner syntax in modern Python.

---

## `-100` label masking in PyTorch

```python
# train.py
labels = input_ids.clone()
labels[0, :prompt_len] = -100
```

The cross-entropy loss in PyTorch ignores positions where the label is `-100` by convention. Setting prompt tokens to `-100` means the model is only penalised for the **completion** tokens — it learns to generate the note sequence, not regurgitate the prompt.

**Coming from C:** `-100` is a magic sentinel value baked into PyTorch's loss implementation. It's effectively a bitmask — "skip this index in the reduction."

**Coming from TS:** No analogy in the language. This is a framework convention: PyTorch's `CrossEntropyLoss` has an `ignore_index` parameter that defaults to `-100`. Any label equal to that value is excluded from the mean.

---

## `scope="module"` in pytest fixtures

```python
# tests/
@pytest.fixture(scope="module")
def tokenizer():
    return AutoTokenizer.from_pretrained(MODEL)
```

Pytest fixtures are setup/teardown helpers injected by name into test functions. The `scope` controls lifecycle:

| scope      | created once per… |
|------------|-------------------|
| `function` | test (default)    |
| `module`   | test file         |
| `session`  | entire test run   |

Use `scope="module"` for expensive objects (model loads, DB connections) you only want to create once per file.

**Coming from C:** Like a global that's lazily initialised before the first test in a translation unit and torn down after the last.

**Coming from TS:** Like `beforeAll` / `afterAll` in Jest scoped to a `describe` block. Pytest's injected-by-name approach replaces explicit `beforeEach` wiring.

---

## Lazy imports inside functions

```python
# build_training.py
def build_hf_dataset(output_dir: Path) -> None:
    from datasets import Dataset, DatasetDict
    ...
```

Python imports can appear anywhere — including inside a function body. The module is only loaded the first time that line executes (then cached). This avoids importing a heavy dependency (`datasets`) unless the function is actually called.

**Coming from C:** No equivalent — `#include` is always at file scope and compile-time. The closest analogy is a DLL loaded on first use (`dlopen` / `LoadLibrary`).

**Coming from TS:** Like a dynamic `import()` but synchronous. In Node.js you'd use `const { Dataset } = await import('datasets')` for the same lazy-load effect.

---

## `@property` decorator

```python
# schema.py
@property
def duration_ms(self) -> float:
    if not self.events:
        return 0.0
    return sum(e.duration_ms for e in self.events)
```

`@property` turns a method into a computed attribute — callers write `table.duration_ms`, not `table.duration_ms()`. The value is recomputed on every access.

**Coming from C:** Like a getter function, but the call-site syntax has no parentheses. Callers can't tell it's computed rather than stored.

**Coming from TS:** Identical to TypeScript's `get` accessor (`get durationMs() { ... }`). Same semantics, Python uses a decorator instead of a keyword.

---

## Raw byte construction for binary formats

```python
# render.py
header = (
    b"MThd"
    + (6).to_bytes(4, "big")       # header length
    + (0).to_bytes(2, "big")       # format 0
    + (1).to_bytes(2, "big")       # 1 track
    + MIDI_PPQ.to_bytes(2, "big")  # ticks per beat
)
```

Python's `bytes` type and `int.to_bytes()` let you construct binary formats without external libraries. `b"MThd"` is a raw byte literal; `(6).to_bytes(4, "big")` packs the integer 6 as a 4-byte big-endian value. Concatenation with `+` joins byte strings.

**Coming from C:** This replaces `fwrite(&val, sizeof(val), 1, fp)` with explicit byte-order control. No struct packing surprises — you choose endianness per value.

**Coming from TS:** Like `Buffer.from()` and `buffer.writeUInt32BE()` in Node.js. Python's approach is more functional — you build immutable byte strings and concatenate them.

---

## Variable-length quantity (VLQ) encoding

```python
# render.py
def _write_vlq(value: int) -> bytes:
    result = []
    result.append(value & 0x7F)
    value >>= 7
    while value > 0:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(result))
```

MIDI uses VLQ to encode delta times compactly: 7 bits per byte, MSB=1 means "more bytes follow." This is the same encoding used in Protocol Buffers (varint) and Git pack files.

**Coming from C:** Identical bit manipulation — shift, mask, set high bit. The only Python-ism is building a list and reversing it rather than writing to a pre-allocated buffer.

**Coming from TS:** Same logic works in JS with `Uint8Array`. The `& 0x7F` / `| 0x80` / `>>= 7` pattern is universal across languages.
