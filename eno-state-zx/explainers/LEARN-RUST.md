# Rust — Quick Reference

Picked up while porting the beeper engines to Rust. Written for someone who knows C.

---

## The basics

Rust looks like C with stricter rules. No header files, no manual memory management, no null.

```rust
fn add(a: i32, b: i32) -> i32 {    // types after the name, -> for return type
    a + b                            // last expression is the return value (no semicolon!)
}
```

**Key difference from C:** variables are immutable by default. Use `mut` to allow changes.

```rust
let x = 5;          // immutable — like C's `const int x = 5;`
let mut y = 10;     // mutable — like C's `int y = 10;`
y += 1;             // fine
// x += 1;          // compile error!
```

---

## Types

| Rust | C equivalent | Notes |
|------|-------------|-------|
| `u8` | `uint8_t` | unsigned 8-bit (0–255) |
| `i32` | `int32_t` | signed 32-bit |
| `f32` | `float` | 32-bit float |
| `f64` | `double` | 64-bit float |
| `bool` | `_Bool` | `true` / `false` |
| `usize` | `size_t` | pointer-sized unsigned |

Rust won't silently convert between types. You have to cast explicitly:

```rust
let period: u8 = 86;
let freq = 3_500_000.0 / (period as f64);  // as = explicit cast
```

Underscores in numbers are allowed for readability: `3_500_000`.

---

## Structs and methods

Like C structs, but methods are attached via `impl` blocks:

```rust
pub struct ToneEngine {
    period: u8,
    counter: u8,
    speaker: bool,
}

impl ToneEngine {
    // "constructor" — just a regular function that returns Self
    pub fn new(period: u8) -> Self {
        Self {
            period,
            counter: period,
            speaker: false,
        }
    }

    // method — takes &mut self (mutable reference to the struct)
    pub fn sample(&mut self) -> f32 {
        self.counter -= 1;
        if self.counter == 0 {
            self.speaker = !self.speaker;
            self.counter = self.period;
        }
        if self.speaker { 1.0 } else { -1.0 }
    }
}
```

**`self` is like `this` in C++:**
- `&self` = read-only reference (`const struct *self`)
- `&mut self` = mutable reference (`struct *self`)
- `self` = take ownership (rare — means the struct is consumed)

---

## Visibility

Everything is **private by default** — opposite of C where everything is visible.

- `pub` makes it accessible outside the module
- No `pub` = only visible within the same file/module

```rust
pub struct ToneEngine {  // visible outside
    period: u8,          // private — only ToneEngine's own methods can access it
}
```

---

## Control flow

Same as C but **no parentheses needed** around conditions:

```rust
if self.counter == 0 {      // no parens!
    self.speaker = !self.speaker;
}

while self.t_accum >= 24.0 {
    self.t_accum -= 24.0;
}

for i in 0..100 {            // 0 to 99 (like `for (int i=0; i<100; i++)`)
    // ...
}

for &(duration, period) in notes {   // iterate a slice, destructure each tuple
    // ...
}

loop {                       // infinite loop (like `while (1)`)
    break;
}
```

**`if` is an expression** — it returns a value:

```rust
let output = if self.speaker { 1.0 } else { -1.0 };
```

---

## Collections

| Rust | C equivalent | Notes |
|------|-------------|-------|
| `Vec<f32>` | `float *buf + size_t len` | Dynamic array (growable, heap-allocated) |
| `&[f32]` | `const float *buf, size_t len` | Slice — borrowed view of contiguous data |
| `&[(u8, u8)]` | — | Slice of tuples (pairs of bytes) |

```rust
let mut output = Vec::new();     // empty dynamic array
output.push(1.0);               // append
output.push(-1.0);

let len = output.len();         // like C's separate length variable
```

**Tuples** are anonymous structs:

```rust
let note: (u8, u8) = (3, 248);   // (duration, period)
let duration = note.0;            // access by index
let period = note.1;

let (d, p) = note;               // destructure into two variables
```

---

## Constants

```rust
const CPU_CLOCK: f64 = 3_500_000.0;         // compile-time constant (like #define but typed)

pub const D_MAJOR_SCALE: [(u8, u8); 16] = [  // fixed-size array of tuples
    (3, 248),   // D4
    (3, 221),   // E4
    // ...
];
```

---

## Tests

Tests live inside the same file, in a `#[cfg(test)]` module. They only compile when you run `cargo test`:

```rust
#[cfg(test)]
mod tests {
    use super::*;     // import everything from the parent module

    #[test]
    fn speaker_is_square_wave() {
        let mut engine = ToneEngine::new(86);
        for _ in 0..1000 {
            let s = engine.sample(44100);
            assert!(s == 1.0 || s == -1.0);
        }
    }

    #[test]
    fn frequency_is_correct() {
        let freq = ToneEngine::freq_for_period(86);
        assert!((freq - 1239.0).abs() < 10.0);
    }
}
```

Run with: `cargo test`

---

## Cargo (the build system)

| Command | What it does |
|---------|-------------|
| `cargo build` | Compile (debug mode) |
| `cargo build --release` | Compile (optimised) |
| `cargo test` | Compile + run all tests |
| `cargo run` | Build + run the binary |
| `cargo run -- --demo` | Run with arguments (everything after `--`) |

Dependencies go in `Cargo.toml` (like package.json). Cargo fetches and compiles them automatically.

---

## Ownership (the big Rust idea)

C trusts you to free memory. Rust tracks it at compile time:

- Each value has exactly **one owner**
- When the owner goes out of scope, the value is freed
- You can **borrow** with `&` (read) or `&mut` (write) — but not both at once

For the beeper engine, this mostly means:
- `&self` = "I'm reading the engine state"
- `&mut self` = "I'm changing the engine state"
- `Vec<f32>` is freed when it goes out of scope — no `free()` needed

You don't need to deeply understand ownership to write beeper engines. If the compiler complains, it's usually telling you to add `&` or `mut`.

---

## Compared to C

| C | Rust |
|---|------|
| `malloc` / `free` | Automatic (ownership) |
| `NULL` | No null. Use `Option<T>` (either `Some(value)` or `None`) |
| `#include "header.h"` | `use crate::module;` or `use super::*;` |
| `printf("x = %d\n", x)` | `println!("x = {x}");` (macros end with `!`) |
| `assert(x == 5)` | `assert_eq!(x, 5);` or `assert!(condition)` |
| Segfault at runtime | Compile error (usually) |
| `struct` + separate functions | `struct` + `impl` block |
| Header files | `pub` keyword on items you want to export |
