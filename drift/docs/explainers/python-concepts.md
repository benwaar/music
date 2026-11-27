# Python Concepts — M2 + M3 Patterns

Patterns and idioms that appear in the codebase and may not be familiar if you're coming from C or TypeScript. Each entry shows the pattern, what it does, and where it shows up.

---

## `@dataclass` for config objects

Python's `dataclass` decorator generates `__init__`, `__repr__`, and `__eq__` from annotated class fields.

```python
@dataclass
class TrainConfig:
    data_dir: str = "_data/segments"
    epochs: int = 50
    batch_size: int = 16
    lr: float = 2e-4
    checkpoint_dir: str = "_data/checkpoints"
    device: str = "auto"
```

`train.py:153–162`

No `__init__` to write. The fields with defaults become keyword arguments. Field annotations are enforced at the IDE/type-checker level (not at runtime — Python doesn't enforce types).

> **Coming from C:** Equivalent to a struct with designated initialiser defaults:
> ```c
> struct TrainConfig { int epochs; float lr; };
> struct TrainConfig cfg = { .epochs = 50, .lr = 0.0002 };
> ```

> **Coming from TS:** Equivalent to an interface + a factory function:
> ```ts
> interface TrainConfig { epochs: number; lr: number; }
> const defaultConfig: TrainConfig = { epochs: 50, lr: 2e-4 };
> ```
> The `@dataclass` does both in one declaration.

---

## `register_buffer` in nn.Module

Attaches a tensor to a module as a non-trainable constant that moves with the model.

```python
self.register_buffer("sqrt_alpha_cumprod", torch.sqrt(alpha_cumprod))
```

`scheduler.py:29`

**The problem it solves:** when you call `model.to(device)`, PyTorch moves all parameters (weights, biases) to the new device. If you store a plain tensor as `self.some_constant = tensor`, it won't move — it stays on whatever device it was created on. If your model is on GPU and the constant is on CPU, the computation fails.

`register_buffer` tells PyTorch: "this tensor isn't trainable, but treat it like a parameter for device management purposes."

Three kinds of module state:

| What | How to store | Moves with `.to(device)`? | Trainable? |
|------|-------------|--------------------------|-----------|
| Weights, biases | `nn.Parameter` (or assigned via `nn.Linear`, etc.) | Yes | Yes |
| Fixed constants (schedule tables, running stats) | `register_buffer` | Yes | No |
| Temporary values, counters | Plain Python `self.x = ...` | No | No |

> **Coming from C:** `nn.Parameter` is like a field in a GPU-managed struct that participates in autodiff. `register_buffer` is like a `const` field in the same struct — managed memory, no gradient.

> **Coming from TS:** Think of `register_buffer` as marking a class property with a custom decorator that hooks into the framework's device-movement lifecycle — analogous to Angular's `@Input()` triggering change detection.

---

## `torch.no_grad()` — decorator and context manager

Disables gradient tracking for a block of code.

**As a decorator** (whole function):

```python
@torch.no_grad()
def generate(model, scheduler, n_samples, device, shape=(1, 128, 176)):
    ...
```

`sampler.py:12`

**As a context manager** (part of a function):

```python
@torch.no_grad()
def update(self, model):
    for name, param in model.named_parameters():
        self.shadow[name].mul_(self.decay).add_(param.data, alpha=1.0 - self.decay)
```

`train.py:75`

**Why it matters:** PyTorch builds a computation graph during every forward pass to enable backpropagation. This graph consumes memory and compute. At inference time (generation, EMA updates) you don't need gradients — `no_grad()` disables the graph construction, making the operation faster and cheaper.

A common bug: running inference without `no_grad()` in a training loop. Memory usage grows because PyTorch keeps the graph alive.

> **Coming from C:** Like disabling instrumentation in a profiling build — the computation runs the same way, but the overhead of recording a trace is eliminated.

> **Coming from TS:** No direct equivalent. Think of it as wrapping code in a "read-only transaction" where no audit log is written.

---

## `F.pad` — dimension ordering (last dim first)

`F.pad` takes a padding spec where dimensions are listed from last to first.

```python
F.pad(x, (0, pad_amount))          # pad last dim: (left, right)
F.pad(x, (0, 3, 0, 2))            # pad last dim then second-to-last
F.pad(x, (1, 1, 1, 1, 0, 0))      # last three dims
```

Our usage (`train.py:46`):

```python
return F.pad(x, (0, pad_amount))
```

Pads the last dimension (time) with `pad_amount` zeros on the right. `0` on the left means no left-padding.

The last-dim-first order is counterintuitive. A mnemonic: think of it as unwinding — you describe the outermost change last and the innermost first, like peeling an onion from the inside out.

> **Coming from C:** `memmove` works on the entire buffer. `F.pad` is higher-level — you specify which axis and how much, and it handles the stride arithmetic.

> **Coming from TS:** CSS padding goes TRBL (top-right-bottom-left). `F.pad` goes last-dim-first, which for a 2D image means `(left, right, top, bottom)` — opposite of CSS. For a 4D tensor `(B, C, H, W)`, `(0, 3)` touches only W.

---

## `if __name__ == "__main__"` — module scripts

Marks code that should only run when the file is executed directly, not when it's imported.

```python
if __name__ == "__main__":
    args = _build_parser().parse_args()
    cfg = TrainConfig(...)
    train(cfg)
```

`train.py:260–272`

When Python imports a module (`from drift.train import train_step`), every top-level statement in that file executes. Without this guard, importing `train.py` would trigger `argparse` argument parsing and start training.

The guard checks `__name__`: when a file is run directly (`python -m drift.train`), `__name__` is `"__main__"`. When it's imported, `__name__` is the module's dotted path (`"drift.train"`).

> **Coming from C:** Equivalent to having a `main()` function. In C, the linker finds `main` as the entry point automatically. In Python, there's no special entry point — the guard is a naming convention that achieves the same thing.

> **Coming from TS:** Like checking `if (require.main === module)` in CommonJS Node, or using a `main()` function that you call at the bottom of the file only outside of tests. ES modules have no equivalent — the idiom is to export everything and have a separate entry-point file.

---

## `*args` unpacking in tensor construction

The `*` operator unpacks a tuple or list into positional arguments.

```python
x = torch.randn(n_samples, *shape)  # sampler.py:34
```

If `shape = (1, 128, 176)`, this expands to `torch.randn(n_samples, 1, 128, 176)`. The `*` splices the tuple's contents into the argument list at that position.

This pattern lets `shape` be a parameter — `generate` accepts any shape tuple and constructs a batch of that size cleanly.

> **Coming from C:** No exact equivalent. Closest is `va_args` variadic functions, but `*args` in Python unpacking is syntactic — the compiler sees the full argument list at compile time; it's just more concise than writing each element.

> **Coming from TS:** Equivalent to the spread operator: `Math.max(...[1, 2, 3])`. Same syntax, same semantics — splice the array into positional arguments.

---

## In-place tensor operations (`mul_`, `add_`)

Methods ending with `_` in PyTorch mutate the tensor in place rather than returning a new one.

```python
self.shadow[name].mul_(self.decay).add_(param.data, alpha=1.0 - self.decay)
```

`train.py:78`

This is the EMA update: `shadow = shadow * decay + param * (1 - decay)`. The in-place version avoids allocating a new tensor, which matters in tight loops (EMA is called every training step).

Equivalent out-of-place:

```python
self.shadow[name] = self.shadow[name] * self.decay + param.data * (1.0 - self.decay)
```

**Footgun:** in-place operations break autograd if applied to a tensor that's part of the computation graph. Safe to use on parameters (`.data`) or buffers, not on intermediate activations inside a `forward()` call.

> **Coming from C:** In-place is the default in C — you write directly to memory. In PyTorch the default is immutable (new allocation), and `_` suffix opts into mutation.

> **Coming from TS:** Arrays and objects are mutable by default in JS/TS, but primitive values and most framework data are treated as immutable. The `_` convention is the explicit opt-in — analogous to Immer's `produce` vs direct mutation.

---

## `hasattr` for duck typing (M3)

Python checks capabilities, not types. The sampler loop in `drift/sampler.py` detects DDIM by checking for a `timesteps` attribute rather than checking the class:

```python
is_ddim = hasattr(scheduler, "timesteps")
if is_ddim:
    timesteps = scheduler.timesteps.tolist()
else:
    timesteps = list(range(start_step - 1, -1, -1))
```

This is duck typing: "if it has a timesteps attribute, treat it as a DDIM scheduler." Any new scheduler that stores a `.timesteps` buffer will work without modifying the sampler.

> **Coming from C:** In C you'd check a type tag or use a union discriminant. Python's approach is closer to checking if a function pointer is non-null in a vtable — "can this object do X?" rather than "is this object type Y?"

> **Coming from TS:** TypeScript does this too — `if ('timesteps' in scheduler)` is a type guard that narrows the type. Python's `hasattr` is the runtime equivalent without compile-time narrowing.

---

## `choices` in argparse (M3)

Restricts an argument to a fixed set of values. Invalid input is rejected with a help message before the script runs.

```python
parser.add_argument("--sampler", choices=["ddpm", "ddim"], default="ddpm")
```

> **Coming from TS:** Like an enum type on a CLI flag — the parser enforces the constraint, not your code. No validation `if` statements needed.

---

## `Path.glob` for file discovery (M5)

`pathlib.Path.glob(pattern)` returns matching paths under a directory. Wrapping in `sorted()` gives a stable, deterministic order.

```python
wav_files = sorted(sample_dir.glob("sample_*.wav"))
# scripts/analyse_m5.py:52 — collect all generated samples for a source/strength combo
```

`glob` patterns use `*` (any chars within a path segment) and `**` (recursive). The returned iterator is unordered — `sorted()` ensures the same order every run, which matters for reproducible analysis.

> **Coming from C:** Similar to `opendir` + `readdir` + `fnmatch`, but as a one-liner. Order from the OS is undefined; `sorted()` is the idiomatic fix.

> **Coming from TS:** Like `fs.readdirSync(dir).filter(f => minimatch(f, pattern))`. `pathlib` is the stdlib equivalent of `glob` / `fast-glob`, returning `Path` objects rather than strings.
