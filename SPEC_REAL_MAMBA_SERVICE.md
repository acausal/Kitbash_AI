# SPEC — Real MambaContextService (swap mock for real BitMamba)

**Date:** 2026-07-11
**Status:** APPROVED FOR IMPLEMENTATION — execute steps in order, no skipping.
**Audience:** implementing model(s). Read the whole document before writing any code. Working rules apply: surgical edits, TEST-/DIAGNOSTIC- prefixes for non-shipping files, paste executed test output — claimed success is not success.
**Priority:** Independent of Mutation 2 / Chat Milestone (those are DONE). This is the follow-up the Chat Milestone Phase B explicitly deferred ("swap the real MambaContextService in place of the mock — that's separate work, possibly its own spec"). Blocks nothing upstream. Can run before or after Docker containerization; containerization should consume this service's interface, not precede it.
**Blocking:** nothing. (Not a Phase 5 critical-path blocker — MambaContextService was YELLOW/mock-accepted; this upgrades it to real.)

---

## 1. Purpose

`SPEC_ONE_REAL_SLEEP_CYCLE.md` and the End-to-End Chat Milestone both ran against `MockMambaService` (the MVP no-op). The user then recalled that a real **BitMamba** framework exists on disk. Investigation (2026-07-11) confirmed:

- **Framework present:** `B:\ai\llm\kitbash\bitmamba.cpp` — BitMamba2 (255M / 1B params), a C++ AVX2 inference library + a Python `scripts/fast_inference.py` that runs the model **in-process via PyTorch** (`DEVICE = cuda if available else cpu`). It is **NOT an HTTP server** (unlike the BitNet `llama-server.exe`).
- **Weights present:** `B:\ai\llm\kitbash\models\bitmamba\` — `bitmamba_1b.bin`, `bitmamba_255m.bin`, plus `.msgpack` checkpoints.
- **No real service implementation exists.** The repo's `src/context/` (and the Kitbash_AI copy `mock_mamba_service.py`) contains **only `MockMambaService`**. The ABC `MambaContextService` defines `get_context(request: MambaContextRequest) -> MambaContext`; no class implements it for real.

So "running BitMamba" (model inference) and "a `MambaContextService` the orchestrator can call" are **two different things**. This spec's job: write the adapter that bridges them, wire it into the factory replacing the mock, and prove it returns a populated `MambaContext`.

## 2. Interface contract (must satisfy exactly)

From `interfaces/mamba_context_service.py` (read before coding):

- `MambaContextRequest` — fields include `user_id`, `session_id`, `user_query`, and a `windows` selector (the four time windows the mock ignores). Confirm the exact field names from the ABC + `query_orchestrator_posix.py:_get_mamba_context` (which already builds `MambaContextRequest(user_id=, session_id=)` — likely needs `user_query=` too).
- `MambaContext` — the return type. Has four time-window slots (the mock returns all empty) + `active_topics`. The real service must populate at least some windows with real context the model produces.
- `MambaContextService` (ABC) — `get_context(request) -> MambaContext`. **Never returns None** (mock contract guarantees this; the real impl must too — orchestrator relies on it).

The orchestrator calls `self.mamba_service.get_context(request)` at `query_orchestrator_posix.py:440`. Swapping is a construction change in `query_orchestrator_factory.py` (where `MockMambaService` is currently instantiated — find the exact site; it was confirmed present at the factory per Chat Milestone recon).

## 3. Step 0 — Decide the runtime shape (DO NOT GUESS)

The framework offers two runtimes; they imply different service designs. Pick ONE with user sign-off before coding:

- **Option A — PyTorch in-process (`fast_inference.py`):** load `BitMambaLM` (scripts/torch_model.py) with a `.bin` weight, run inference in the orchestrator's own Python process. Pros: simplest, no IPC. Cons: couples torch model + `transformers` into the orchestrator venv; blocks the query thread on model fwd-pass; the venv currently has torch 2.13.0+cpu but **may lack `transformers`** (verify in Step 0).
- **Option B — C++ binary / subprocess:** build `bitmamba.cpp` (CMakeLists.txt present; needs AVX2 x86 build) and wrap it behind a small service (stdio/pipe or a lightweight HTTP shim) so `get_context()` shells out / POSTs. Pros: keeps heavy model out of the orchestrator; matches the BitNet pattern. Cons: build step + IPC plumbing; more code.

The Chat Milestone spec forbade swapping a real component "without asking first (that's separate work, possibly its own spec)." This spec IS that separate work — but the **runtime choice (A vs B)** is still a design decision the implementing model must not silently make. **Resolve it in Step 0 with the user; record the choice in this file before coding.**

*Acceptance:* runtime choice recorded (A or B), with the reason, before Step 1.

### Step 0 decision — RECORDED 2026-07-11
- **Choice: Option B** — C++ binary / subprocess behind a lightweight shim; the orchestrator shells out to (or POSTs at) a separate BitMamba process. NOT in-process PyTorch.
- **Reason (user):** BitMamba has already been run successfully "with what the drive has already," at least to chat with, so the C++/subprocess path is known-good on this machine — lower risk than standing up an in-process torch stack. Additionally, the SSM-in-ternary-model field has split across different underlying frameworks, so the underlying engine may need swapping later; Option B's process isolation makes that a shim change, not an orchestrator rewrite. This also aligns with the user's stated isolation/containerization preference.
- **Consequences:** `real_mamba_service.py` wraps a subprocess/HTTP shim, it does NOT load torch in-process. The venv `transformers` gap is therefore not on the critical path for B. Requires a build step (CMake + AVX2) and IPC plumbing in Steps 1–2. Model/paths stay config-driven (not hardcoded to `B:\`).

## 4. Step 1 — Verify environment for the chosen runtime

- Option A: confirm `transformers` + the bitmamba `torch_model.py` import cleanly in `.venv`; load `bitmamba_255m.bin` (smaller, faster to validate) and run one fwd-pass on a sample `user_query`. Report model load time + a sample output.
- Option B: build `bitmamba.cpp` (`cmake` + `make`); confirm the binary runs and accepts input. Report build commands + a sample run.
- For BOTH: confirm the four `MambaContext` windows can be populated from the model's actual output (BitMamba is a sequence model — its hidden state / next-token context is the natural source for temporal-window context). If the model output doesn't map cleanly to the four windows, STOP and report the mapping gap rather than fabricating window contents.

*Acceptance:* chosen runtime loads/runs a model and produces output that can populate at least one `MambaContext` window; evidence pasted.

### Step 1 grounding — RECORDED 2026-07-11 (read-only investigation, no build yet)
- **CLI shape (`examples/main.cpp`):** one-shot executable. Signature
  `./bitmamba <model.bin> "<prompt>" <mode> [temp] [penalty] [min_p] [top_p] [top_k] [max_tokens] [output_mode]`.
  `mode` = `tokenizer` (text in/out) or `raw` (token IDs). `output_mode=clean` → stdout carries ONLY the generated text (no `[INFO]`/`[STATS]` noise); all diagnostics go to stderr. The model is loaded **fresh on every invocation** (`BitMambaModel model(argv[1])` at main.cpp:105) — the binary is **stateless / no persistent server**. **Constraint:** `tokenizer.bin` MUST sit in the same directory as the exe (main.cpp:121) — packaging must copy it next to the built binary (or run the exe from the source dir).
- **Build:** `CMakeLists.txt` present, builds a `bitmamba` lib + `bitmamba` CLI (`build/bitmamba`). Flags: `-O3 -march=native -fopenmp` → **must compile on this machine** (native tuning); a copied prebuilt exe from another box would be wrong. `cmake` IS on PATH (`C:\Program Files\CMake\bin\cmake`) but **`g++`/`gcc`/`make` are NOT** — CMake may fail to find a C++ toolchain. Need to confirm a compiler is available (VS MSVC cl.exe? or install MinGW/g++) before the build will succeed. **Open risk, not yet resolved.**
- **Weights:** already on disk at `B:\ai\llm\kitbash\models\bitmamba\` — `bitmamba_1b.bin` (644 MB), `bitmamba_255m.bin` (258 MB), plus `.msgpack` sources. `.bin` files exist, so **no `export_bin.py` step needed** if they are valid for this build (verify at build time). 255M is the smaller/faster validation target.
- **Toolchain (PROBED 2026-07-11):** NO MinGW `g++`/`gcc`, NO standalone MSVC `cl.exe` found via vswhere. **clang/clang++ IS present** at `C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\Llvm\x64\bin\` (VS-bundled LLVM 18 → reports Clang 20.1.8). CMake default generator = "Visual Studio 18 2026". The `CMakeLists.txt` flags `-O3 -march=native -fopenmp` are **GCC/Clang flags** — clang-cl understands them (maps `-march=native`→native, supports `-fopenmp`), but MSVC `cl.exe` does not (`/arch:AVX2`, `/openmp`). **Build path: `cmake -G "Visual Studio 18 2026" -T clangcl -B build`** (clang-cl under the VS generator), then build the `bitmamba` lib + a new `bitmamba_server` target. **Configure-only probe SUCCEEDED (RC=0):** Clang 20.1.8 identified via clang-cl, build files generated. NOTE: CMake (native Win binary) requires Windows-style paths (`B:\...`), not msys `/b/...`. Probe dir removed after.
- **BUILD + SMOKE (EXECUTED 2026-07-11, SUCCESS):** Added `examples/bitmamba_server.cpp` (persistent TCP shim: loads model+tokenizer once, answers line-delimited prompts on `127.0.0.1:<port>`, returns generated text clean) + `bitmamba_server` CMake target (`target_link_libraries(... ws2_32)`). Built `bitmamba_server` (Release, clang-cl) → `build/Release/bitmamba_server.exe` (133 KB). Warnings only (`-fopenmp`→`-openmp` ignored by clang-cl; `inet_addr` deprecation — harmless). **Smoke test PASSED:** ran server with `bitmamba_255m.bin` on port 8731 (model+tokenizer loaded once, "listening on 127.0.0.1:8731"); Python client sent "The capital of France is" → coherent generated text returned; a SECOND request answered without model reload (warm). Server stopped after test. **Verdict: Option B2 runtime works end-to-end.** Path note: exe must run from a dir containing `tokenizer.bin` (copied beside exe, or launch from source dir).
- **IPC design sub-decision (B1 vs B2) — CHOICE: B2 (2026-07-11, user)**
  - **B1 (per-call shell-out):** `real_mamba_service.py` calls the CLI via `subprocess` on each `get_context()`, passes the prompt, reads stdout. Minimal code, matches the existing CLI exactly. Cost: the model **reloads every call** (model load is not free) → slow per query.
  - **B2 (persistent shim):** write a tiny long-running wrapper (keep `BitMambaModel` loaded; answer requests over stdio/TCP) so `get_context()` talks to a warm process. No per-call reload, true isolation + swappable engine — but more code (the wrapper + the Python client).
  - **Picked B2:** user's reason for Option B was future SSM/ternary-framework swappability; a persistent, isolated process best honors that (engine swap = shim change, not orchestrator change). Implementation: a small C++ server program (`bitmamba_server`, links `bitmamba_lib`) that loads the model once and answers requests over a local socket/stdio; `real_mamba_service.py` is the Python client. Build target added to `CMakeLists.txt`.

## 2b. DECISION REGISTER — likely to revisit

Two decisions in this spec are provisional and expected to need re-examination later. Recorded so they are not silently treated as permanent.

### D1 — IPC shape: Option B2 (persistent shim) over B1 (per-call shell-out)
- **Made:** 2026-07-11 (user). Built `bitmamba_server` (C++ TCP shim) + `real_mamba_service.py` client.
- **Why:** user's stated reason for Option B was that the SSM/ternary-model field is splitting across underlying frameworks, so isolation (engine swap = shim change, not orchestrator change) was worth the extra code.
- **Revisit triggers:**
  - The SSM/ternary framework split the user anticipated actually happens and a *different* runtime shape (e.g. an HTTP-capable engine, or in-process) becomes clearly better → re-evaluate B1 or a new B3.
  - The shim's per-connection "load model once, generate, close" design proves too slow / the TCP line protocol needs to become request/response framed (currently newline-delimited, single prompt per connection) → protocol or transport change.
  - Operational burden of managing a separate process (launch/crash/restart) outweighs isolation benefit → reconsider B1.
- **What protects us:** the shim boundary means changing the engine = editing `bitmamba_server.cpp` / `CMakeLists.txt` (engine tree, outside repo), NOT `real_mamba_service.py` or the orchestrator.

### D2 — Window mapping: Option 1 (context_1hour only; 1day/72h/1week left empty; active_topics heuristic)
- **Made:** 2026-07-11 (user approved "Option 1 + refinement"). Implemented in `real_mamba_service.py`.
- **Why:** BitMamba (as wired) is **stateless** — one-shot generation off the prompt, no cross-query memory. So only `context_1hour` (most recent) can be honestly populated; fabricating the three longer windows would violate the spec's "populate honestly / no mock-shaped placeholders" rule. `user_query` is forwarded so the generation is query-relevant. `active_topics` is a crude regex extractor (capitalized/long words, stopword-filtered), not semantic.
- **Revisit triggers:**
  - **Stateful memory lands (mock docstring names "Phase 4 → Real Mamba with stateful hidden_state swapping").** Once the model can carry cross-query hidden state, the 1day/72h/1week windows should be populated from real temporal context — at which point Option 1's "leave empty" rule must be lifted and D2 re-decided.
  - The crude `active_topics` heuristic proves noisy/unuseful in production → replace with a proper extractor (or drop `active_topics` and rely on `context_1hour` text).
  - A downstream consumer actually reads `context_1day/72hours/1week` and needs content there → either wire real memory or explicitly document the windows as intentionally unused.
- **Current honest gap:** the three longer windows are empty BY DESIGN. Do not "fill them" to satisfy a consumer without real temporal data.

### D3 — Build toolchain pinned to clang-cl / VS2026 generator (environment-specific)
- **Made:** 2026-07-11 (discovered, not a user choice). No MinGW/MSVC `cl.exe`; clang-cl 20.1.8 (VS-bundled) is the only working compiler. CMake requires Windows-style `B:\` paths. `-fopenmp` is ignored by clang-cl (MSBuild sets OpenMP).
- **Revisit triggers:** a MinGW or real MSVC toolchain is installed → re-evaluate the generator/flags; the `CMakeLists.txt` `-O3 -march=native -fopenmp` are GCC/Clang flags and would need adjustment for a pure-MSVC build.
- **Note:** this is environment-specific, not a design decision, but it is the reason the engine only builds on this machine as configured.

### Step 0 decision — RECORDED 2026-07-11

New file: `real_mamba_service.py` (Kitbash_AI root, alongside `mock_mamba_service.py`). Subclass `MambaContextService`, implement `get_context(request) -> MambaContext`:

- Lazily load the model once (not per-call) — guard the load; on load failure, **do not crash the orchestrator**; fall back to an empty `MambaContext` (matching the mock's safe behavior) and log a warning. The orchestrator must survive a missing/!broken Mamba model.
- Map the model's context output into the four `MambaContext` windows + `active_topics`. Populate honestly — if a window has no real data, leave it empty (do NOT fill with mock-shaped placeholders).
- Honor `windows` selector if the ABC/request supports it; otherwise populate all windows the model can fill.
- **Never return None.**

Keep it config-driven (NOT hardcoded to `B:\...`): model path / runtime flags come from a constructor arg or an env/config, defaulting to sensible values but overridable. This directly addresses the user's stated concern about not hardwiring local filesystem layout.

*Acceptance:* `RealMambaService` constructed; `get_context()` on a sample request returns a non-None `MambaContext` with ≥1 window populated (for a real model) or empty (for a safe fallback) — never None.

## 6. Step 3 — Write the contract test

New file: `TEST-real_mamba_service.py`. Assert:

- `RealMambaService` is a `MambaContextService` subclass; `get_context()` returns `MambaContext`, never None.
- With a real model loaded: ≥1 window populated for a sample `user_query`; window contents are derived from model output (assert they are not the mock's constant-empty shape when a model is present).
- **Graceful degradation:** construct with a deliberately broken/invalid model path → `get_context()` returns an empty-but-valid `MambaContext` (no exception escapes). This proves the orchestrator won't crash if BitMamba is unavailable.
- Swap-in wiring smoke (optional): `create_query_orchestrator(mamba_service=RealMambaService(...))` builds and a `process_query()` still returns without crashing (the orchestrator already calls `get_context` at :440).

*Acceptance:* test runs, all assertions pass, raw output pasted.

## 7. Step 4 — Wire into the factory + update SOCKET_MAP

- In `query_orchestrator_factory.py`, replace the `MockMambaService()` instantiation with `RealMambaService(...)` (config-driven path). Keep the mock import available for a fallback/tests, but the default production construction uses the real service.
- Update `SOCKET_MAP.md` MambaContextService row: YELLOW (mock only) → GREEN (real BitMamba wired), citing this spec + the test. Note the runtime choice (A/B) and any degradation caveat.

*Acceptance:* factory diff pasted; SOCKET_MAP excerpt pasted.

## 8. Step 5 — Report honestly

One paragraph: does the real Mamba now answer `get_context()` with populated windows, and does the orchestrator survive a missing model? If the model output couldn't map to the four windows, name that gap precisely. Do not round a partial mapping up to "Mamba works."

## 9. Explicitly out of scope

- Changing `MambaContext` / `MambaContextRequest` shapes (use them as-is; if they're wrong, that's a separate schema spec).
- Changing `rule_based_triage.py` or the cascade (BitNet routing is a separate follow-up).
- Building the Docker image for BitMamba — this spec makes the service config-driven so containerization can consume it later; the container itself is separate infra work.
- Fixing the negative `mtr_confidence` / `trace_logged=False` findings from the Chat Milestone — separate follow-ups.
- De-hardcoding `bitnet_engine.py`'s `B:\` paths — separate follow-up (referenced here only because both are "local-fs hardcoding" items; do not fix in this spec).

## 10. Done-when

`real_mamba_service.py` exists and implements `get_context()` returning a non-None `MambaContext` (populated when a real model loads, safely empty on failure); `TEST-real_mamba_service.py` passes with raw output pasted; factory wired to the real service (config-driven); SOCKET_MAP MambaContextService row flipped to GREEN with this spec cited; Step 5 honest verdict delivered.

---

## Grounding evidence (from 2026-07-11 investigation — do not re-derive blindly)

- BitMamba framework: `B:\ai\llm\kitbash\bitmamba.cpp` (README: BitMamba2 255M/1B, AVX2 x86 C++ + PyTorch `scripts/fast_inference.py`; `DEVICE=cuda if available else cpu`).
- Weights: `B:\ai\llm\kitbash\models\bitmamba\` (`bitmamba_1b.bin`, `bitmamba_255m.bin`, `bit_mamba_1b.msgpack`, `bitmamba_255m.msgpack`). `export_bin.py` converts `.msgpack`→`.bin`.
- Repo has only `MockMambaService` (confirmed: `src/context/mock_mamba_service.py`; Kitbash_AI `mock_mamba_service.py`). No real impl.
- Orchestrator call site: `query_orchestrator_posix.py:440` → `self.mamba_service.get_context(request)`.
- Chat Milestone Phase B (3569281) confirmed factory wires mock; real swap deferred to "its own spec."
- **Open risk to verify in Step 0:** the orchestrator `.venv` has torch 2.13.0+cpu but `transformers` was NOT in the KITBASH_PREREQUISITES import grep — Option A may need `pip install transformers` (or the bitmamba `torch_model.py` may avoid the `transformers` dep; read `scripts/torch_model.py` imports in Step 0).
