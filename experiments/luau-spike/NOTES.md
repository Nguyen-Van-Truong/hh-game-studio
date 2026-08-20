# WP-M-1-b — Luau sandbox + deadline + mutation buffer (spike)

Date: 2026-08-16. Machine: Windows 10/11, rustc 1.93.1 (01f6ddf75 2026-02-11).
Not production. Numbers below are measured in this crate, not claims (I13).

## Crate versions (exact, from Cargo.lock)

| crate | version | notes |
|---|---|---|
| mlua | **0.11.6** | features = `["luau"]` only. `luau` is auto-vendored (do **not** also set `vendored` — that flag is for PUC-Lua / LuaJIT via lua-src). No `send`, `async`, `luau-jit`. |
| mlua-sys | 0.10.0 | pulled by mlua 0.11.6 |
| luau0-src | **0.18.3+luau709** | vendored Luau **0.709** (cc crate compiles C++ sources) |
| Lua `_VERSION` | `Luau 0.709` | printed by `sandbox_and_memory_limit_are_configured` |

Pinned in `Cargo.toml`: `mlua = { version = "0.11.6", features = ["luau"] }`.
Standalone crate — **not** a workspace member of the repo root.

## How sandbox / memory / interrupt are configured

Constructor (`SpikeVm::new`):

1. `Lua::new_with(StdLib::ALL_SAFE, LuaOptions::default())`
2. `lua.set_memory_limit(64 * 1024 * 1024)` — 64 MiB (MASTER 2.5 / 7.3)
3. `lua.set_interrupt` — at Luau **safepoints** (loop back-edge / call / return; "eventually", not every N instructions)
4. Register `gs.set_position` / `gs.set_x` / `gs.set_y` / `gs.touch` on globals
5. `lua.sandbox(true)` **last** so `gs.*` is already on the then-frozen globals

Deadline interrupt (real mlua API, not invented):

- Callback signature: `Fn(&Lua) -> Result<VmState>`
- Under budget: `Ok(VmState::Continue)`
- Over budget: set host cancel flag, then `Err(Error::RuntimeError("deadline exceeded"))`
- **Never** `VmState::Yield` to abort. Yield suspends a coroutine so it can be resumed; it is not a death sentence (MASTER 7.3 / C7).

Host death sentence (MASTER 7.6): after the chunk returns, if the cancel flag is set the callback is `CallbackError::Deadline` even if Lua `pcall` swallowed the error. Buffer is discarded in that path.

Compile: `lua.load(source)` text only. No bytecode load (I4).

Mutation buffer: every `gs.set_*` appends to a pending vec. `commit` only if the chunk returns OK **and** cancel is clear. Script error or deadline → `discard` (world unchanged).

## Test names + pass evidence

Command (from `experiments/luau-spike`, after `vcvars64.bat` — see Windows):

```
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test -- --nocapture
```

2026-08-16 result:

```
running 5 tests
Luau _VERSION = Luau 0.709
test tests::sandbox_and_memory_limit_are_configured ... ok
test tests::mutation_buffer_commit_on_success_discard_on_fail ... ok
test tests::infinite_loop_stopped_by_deadline ... ok
interrupt overhead: with=55.5286ms without=7.9994ms hits=200001 extra_ns=47529200 ns_per_interrupt=237.6
test tests::interrupt_overhead_measurement ... ok
pcall-pierce (retry loop): lua_ok=false cancelled=true interrupts=325240 elapsed=80.077ms
pcall-pierce (single pcall): lua_ok=false cancelled=true touched_after_pcall=false interrupts=232441 elapsed=50.132ms
test tests::pcall_does_not_swallow_deadline ... ok

test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.14s
```

clippy: clean (`-D warnings`). fmt: clean.

Required cases:

| # | test | result |
|---|---|---|
| 1 | `infinite_loop_stopped_by_deadline` | `while true` stopped by ~50 ms budget; wall time < 3 s |
| 2 | `pcall_does_not_swallow_deadline` | pcall around the death loop does **not** let the callback succeed |
| 3 | `mutation_buffer_commit_on_success_discard_on_fail` | success commits `(10,20)`; `error("boom")` and deadline leave world at last commit |

## pcall-pierce: YES

Evidence from `pcall_does_not_swallow_deadline` (2026-08-16):

- Retry-`pcall` + outer `while true`: callback failed (`CallbackError::Deadline`), `lua_ok=false`, `cancelled=true`, world unchanged.
- Single `pcall(function() while true do end end)` then `gs.touch()` + `gs.set_position(1,1)`: `lua_ok=false`, `cancelled=true`, **`touched_after_pcall=false`** — the host function after `pcall` never ran. World stayed `(0,0)`.

So on mlua 0.11.6 + Luau 0.709, an interrupt `Err` is a death sentence the inner `pcall` does not continue past (chunk fails; no post-pcall mutation). The host cancel-flag check is still applied (MASTER 7.6 fallback) and is what the test asserts on.

## Interrupt overhead (measured)

Workload: `for i = 1, 200000 do s += i end`. Interrupt checks `Instant::now()` vs deadline on every safepoint.

| profile | with interrupt | without interrupt | hits | extra | extra / hit |
|---|---|---|---|---|---|
| debug (`cargo test`) | 55.5286 ms | 7.9994 ms | 200001 | 47.5 ms | **238 ns/interrupt** |
| release (`cargo test --release`) | 13.4377 ms | 3.0524 ms | 200001 | 10.4 ms | **52 ns/interrupt** |

Release run (same machine, 2026-08-16):

```
interrupt overhead: with=13.4377ms without=3.0524ms hits=200001 extra_ns=10385300 ns_per_interrupt=51.9
```

Rough takeaway for M3 budgeting: a 200k-iteration loop paid ~10 ms extra in release for ~200k safepoint checks (~52 ns each, dominated by `Instant::now()`). This is a spike measurement, not a production SLO. Sampling Instant every N hits is a later optimization if a frame budget needs it — not done here.

## Windows build pain

- Regular PowerShell: `cl` **not** on PATH. VS 2022 Build Tools **are** installed (`C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools`).
- Need `vcvars64.bat` before `cargo test` so `cc` can compile `luau0-src` (C++).
- cmake 4.3.1 is present but unused; luau0-src builds via the `cc` crate.
- First vendored compile: ~40 s debug / ~1 min 20 s included in the release test build. Incremental Rust is fast after that.
- No missing headers / CRT issues once vcvars is loaded. No need for `luau-jit`.

Team recipe:

```
cmd /c "\"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat\" && cargo test"
```

from `experiments/luau-spike`.
