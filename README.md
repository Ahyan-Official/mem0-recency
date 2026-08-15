# mem0-recency

**A one-line add-on for [Mem0](https://github.com/mem0ai/mem0) that drops stale facts when a user corrects them, so your agent stops answering with information it was already told is outdated.**

You tell your assistant you moved cities. A few turns later it still uses the old one, because Mem0 stored *both* facts and semantic search surfaced the stale one. `mem0-recency` catches the contradiction when the new fact arrives and removes the superseded memory, so only the current value is left behind.

```python
from mem0 import Memory
from mem0_recency import RecencyMemory

memory = RecencyMemory(Memory())          # same Mem0 API, one wrap

memory.add("I live in Detroit", user_id="alice")
memory.add("Actually I moved to Austin", user_id="alice")
# -> the stale "lives in Detroit" memory is removed; the agent now answers "Austin"
```

That's the whole idea. Wrap your existing Mem0 object once. Remove the wrapper and you're back to stock Mem0, no fork, no lock-in.

---

## Why this exists

A 2026 paper named a failure that anyone who's used a memory-enabled assistant has probably felt:

> **Supersede: Diagnosing and Training the Memory-Update Gap in LLM Agents**
> Vedant Patel, 2026. arXiv:[2606.27472](https://arxiv.org/abs/2606.27472)

The paper's finding, in plain terms: when an agent maintains a compact, self-managed memory (instead of re-reading the whole conversation every time), it systematically keeps acting on facts that have since changed. Accuracy on *updated* facts drops from **92% to 77%** even on a frontier model, and falls toward **28%** as the conversation grows across dozens of sessions. A bigger model doesn't fix it. A bigger memory doesn't fix it. The bottleneck is memory *maintenance*, old values that never get overwritten.

**Where this tool fits, and where it doesn't.** This is important, so it's stated up front rather than buried:

- The paper's *hardest* case is **implicit, paraphrased** updates squeezed out of a tiny bounded memory over ~48 sessions. The paper shows that case is only moved by **training a model**, and the author released exactly that: an open RL environment ([github.com/Vrin-cloud/supersede](https://github.com/Vrin-cloud/supersede)). To use it, you retrain.
- `mem0-recency` targets the **everyday, practical** case instead: a user makes a correction in a live app, and you want the stale fact gone *now*, without retraining anything. It's a drop-in utility, not a research method.

So: the author diagnosed the problem and shipped a training environment for the frontier of it. This ships the one-line thing a working developer can `pip install` into a Mem0 app today. Different jobs. Both useful.

Mem0's current pipeline is largely **additive**, new facts are added, older contradictory ones often aren't removed. That's the specific behavior this add-on cleans up.

---

## What's actually verified

Every claim below maps to a script in [`proof/`](proof/) you can run yourself. Nothing here is asserted without a runnable check, and the scope of each proof is stated honestly.

### 1. The problem is real on real Mem0, [`proof/01_does_mem0_fail.py`](proof/01_does_mem0_fail.py)

Feed real, open-source Mem0 a correction and inspect what it keeps:

```
Step 1: user says they live in Detroit
Step 2: user corrects it, they moved to Austin

Mem0 currently stores:
   • User lives in Detroit                                    ← STALE, still present
   • User moved from Detroit to Austin around July 14, 2026   ← new fact

VERDICT: Mem0 kept BOTH. The stale "Detroit" can resurface.
```

A later query for "where does the user live?" returns both values, leaving the model to guess which is current.

<!-- Add your screenshot of proof 01 here -->

### 2. The contradiction detector is trustworthy, [`proof/02_detector_works.py`](proof/02_detector_works.py)

The detector has to do two things: catch a real correction, **and** leave facts that should coexist alone (deleting a fact that should stay is worse than doing nothing). Tested both directions:

```
[PASS] User lives in Detroit    -> User moved to Austin        (change: remove old)
[PASS] User drives a Mazda      -> User switched to a Kia       (change: remove old)
[PASS] User is vegetarian       -> no longer vegetarian         (change: remove old)
[PASS] User likes hiking        -> User likes sushi             (coexist: keep both)
[PASS] User has a dog named Rex -> User has a cat named Milo     (coexist: keep both)
...
10/10 correct
```

<!-- Add your screenshot of proof 02 here -->

### 3. The wrapper removes the stale fact safely, [`proof/03_wrapper_fixes_it.py`](proof/03_wrapper_fixes_it.py)

Same real Mem0 as proof 01, now wrapped. The stale fact is removed, and critically, **memory is never emptied and the just-added fact is never deleted** (an earlier naive version could do both; the wrapper now guards against it):

```
[recency] superseded: 'User lives in Detroit' -> 'User moved to Austin'
final memory:
   • User moved to Austin around July 14, 2026
```

<!-- Add your screenshot of proof 03 here -->

### 4. It still works when the correction is buried, [`proof/04_buried_corrections.py`](proof/04_buried_corrections.py)

A correction, then **buried under 8 unrelated distractor turns**, then queried. Three independent fact types:

```
Scenario: Where does the user live?          current 'austin' present: True   PASS
Scenario: What car does the user drive?      current 'kia' present: True      PASS
Scenario: What is the user's favorite drink? current 'tea' present: True      PASS

3/3 scenarios passed.
```

Honest note: these are **explicit corrections** with a handful of distractors, not the paper's extreme regime (implicit updates, ~48 sessions, tiny bounded memory). This proves the tool holds up on realistic app-length conversations, not that it closes the paper's full gap.

<!-- Add your screenshot of proof 04 here -->

---

## How it works

`mem0-recency` wraps your Mem0 object and changes only `add()`:

1. Mem0 stores the new fact as usual.
2. The wrapper searches existing memories (same user) for candidates that might be contradicted.
3. For each candidate, an LLM-based detector asks: *does the new fact replace this one for the same attribute of the same subject?*
4. If yes, and only if it's a genuinely older, non-duplicate fact, and removing it won't empty the store, the stale memory is deleted.

Every other Mem0 method (`search`, `get_all`, `delete`, …) passes straight through unchanged.

**Safety guarantees** (enforced in [`mem0_recency/wrapper.py`](mem0_recency/wrapper.py), covered by the proofs):

- Never deletes the fact that was just added.
- Never lets memory become empty.
- Skips near-duplicate rephrasings, so two versions of the *same current fact* don't trigger a delete.

---

## Install

```bash
pip install mem0ai        # your existing memory layer
pip install openai        # used by the detector
# then install this add-on (from source until published to PyPI):
pip install git+https://github.com/Ahyan-Official/mem0-recency.git
```

## Usage

```python
from mem0 import Memory
from mem0_recency import RecencyMemory

memory = RecencyMemory(
    Memory(),
    verbose=True,                                  # log each supersession
    on_supersede=lambda old, new: print(old, "->", new),
)

memory.add("I drive a Mazda", user_id="alice")
memory.add("I sold the Mazda and now drive a Kia", user_id="alice")
# the "Mazda" memory is removed; "Kia" remains
```

Set `OPENAI_API_KEY` in your environment (the detector uses `gpt-4o-mini` by default).

## Reproduce the proofs yourself

```bash
git clone https://github.com/Ahyan-Official/mem0-recency.git
cd mem0-recency
python -m venv .venv && source .venv/bin/activate
pip install mem0ai openai chromadb
echo "OPENAI_API_KEY=sk-..." > .env

python proof/01_does_mem0_fail.py       # Mem0 keeps the stale fact
python proof/02_detector_works.py       # 10/10 detector accuracy
python proof/03_wrapper_fixes_it.py     # wrapper removes it safely
python proof/04_buried_corrections.py   # holds under buried corrections
```

## Scope and honest limitations

This is a **v0.1 proof of concept**, a practical utility, verified on real open-source Mem0 with real API calls. It is deliberately **not** a claim to solve the full supersession gap. Specifically:

- **It handles explicit corrections, not the paper's hardest case.** The paper's core failure, implicit, paraphrased updates lost from a small bounded memory over ~48 sessions, is *not* what this addresses. That regime is the subject of the author's own RL training environment. Templated/explicit updates like the demos here are, per the paper, the comparatively easy case; this tool automates cleaning them up inside Mem0, which Mem0 doesn't do on its own.
- **The proofs are a handful of hand-chosen scenarios**, not a benchmark. A rigorous claim would need dozens of cases and a head-to-head number (stale-retrieval rate with vs. without the wrapper). See Roadmap.
- **Detection costs an LLM call** per candidate contradiction. Fine for typical apps; worth noting at high volume. (There's active research, arXiv:2606.01435, arguing a *deterministic* recency rule can beat an LLM here; a deterministic backend is on the roadmap partly to test that.)
- **Mem0's fact extraction is non-deterministic** (LLM-driven), so stored wording varies run to run. The wrapper is built to be safe across that variance, but it acts on whatever Mem0 produces.
- **It acts on `add()` going forward**, it does not retroactively clean memories written before you wrapped the object.

If you hit a case where it deletes something it shouldn't, or misses a stale fact, please open an issue with the sequence of `add()` calls.

## Roadmap

- A real benchmark: stale-retrieval rate on the LongMemEval knowledge-update subset, plain Mem0 vs. this wrapper vs. a deterministic-recency baseline.
- A deterministic (no-LLM) detector backend, for zero-cost use and to test the claim in arXiv:2606.01435.
- Optional "keep history" mode that moves stale facts to metadata instead of deleting them.

## Credits

Built on the problem diagnosed in Patel, 2026 ([arXiv:2606.27472](https://arxiv.org/abs/2606.27472)), whose open RL environment ([Vrin-cloud/supersede](https://github.com/Vrin-cloud/supersede)) targets the training side of the same gap. Wraps [Mem0](https://github.com/mem0ai/mem0). Not affiliated with either.

## License

Apache-2.0
