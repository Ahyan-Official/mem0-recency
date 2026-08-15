# mem0-recency

**An add-on for [Mem0](https://github.com/mem0ai/mem0) that removes stale facts, so your agent stops answering with information the user already corrected.**

You tell your assistant you moved to Austin. Several turns later it still says you live in Detroit — because Mem0 stored *both* facts and semantic search surfaced the old one. `mem0-recency` catches the contradiction when the new fact arrives and removes the superseded memory, so only the current value survives.

```python
from mem0 import Memory
from mem0_recency import RecencyMemory

memory = RecencyMemory(Memory())          # same Mem0 API, one wrap

memory.add("I live in Detroit", user_id="alice")
memory.add("Actually I moved to Austin", user_id="alice")
# -> the stale "lives in Detroit" memory is removed; the agent now answers "Austin"
```

---

## The problem this solves

Agents built on compact, self-managed memory (instead of re-reading the entire conversation) systematically answer with **outdated** facts. This isn't a hypothetical — it was measured and named.

> **Supersede: Diagnosing and Training the Memory-Update Gap in LLM Agents**
> Vedant Patel, 2026. arXiv:[2606.27472](https://arxiv.org/abs/2606.27472)

The paper shows that when an agent must maintain a bounded memory rather than re-read full context, accuracy on *updated* facts drops sharply — from **92% to 77%** even on a frontier model — and collapses toward **28%** as the conversation grows. Critically, the paper demonstrates that **a bigger model does not fix it, and a bigger memory does not fix it either.** The failure is memory *maintenance*: old values that never get overwritten. (Related prior work: [Search-Time Data Contamination, Scale AI, 2025](https://arxiv.org/abs/2508.13180); Mem0's own [ECAI 2025 paper](https://arxiv.org/abs/2504.19413).)

Mem0's current pipeline is **strictly additive** — new facts are added, not overwritten. That is exactly the failure mode above. `mem0-recency` adds the missing overwrite step **without forking Mem0**: it wraps the memory object you already use.

---

## This is not a claim — it's reproduced

Every step below is a script in [`proof/`](proof/) that you can run yourself. Nothing here is asserted without a runnable check.

### 1. The gap is real on real Mem0 — [`proof/01_does_mem0_fail.py`](proof/01_does_mem0_fail.py)

Feed real, open-source Mem0 a correction and inspect what it stores:

```
Step 1: user says they live in Detroit
Step 2: user corrects it — they moved to Austin

Mem0 currently stores:
   • User lives in Detroit                                    ← STALE, still present
   • User moved from Detroit to Austin around July 14, 2026   ← new fact

VERDICT: Mem0 kept BOTH. The stale "Detroit" can resurface.
```

Mem0 keeps the outdated fact alongside the new one. A query for "where does the user live?" returns both.

<!-- Add your screenshot of proof 01 here -->

### 2. The contradiction detector is trustworthy — [`proof/02_detector_works.py`](proof/02_detector_works.py)

The detector must catch real supersessions **and** leave coexisting facts alone (deleting a fact that should stay is worse than doing nothing). Tested both directions:

```
[PASS] User lives in Detroit   -> User moved to Austin        (stale: remove)
[PASS] User drives a Mazda      -> User switched to a Kia       (stale: remove)
[PASS] User is vegetarian       -> no longer vegetarian         (stale: remove)
[PASS] User likes hiking        -> User likes sushi             (coexist: keep)
[PASS] User has a dog named Rex -> User has a cat named Milo     (coexist: keep)
...
10/10 correct
```

<!-- Add your screenshot of proof 02 here -->

### 3. The wrapper fixes it safely — [`proof/03_wrapper_fixes_it.py`](proof/03_wrapper_fixes_it.py)

Same real Mem0 as proof 01, now wrapped. The stale fact is removed — and critically, **memory is never emptied and the just-added fact is never deleted** (an earlier naive version could do both; the wrapper now guards against it):

```
[recency] superseded: 'User lives in Detroit' -> 'User moved to Austin'
final memory:
   • User moved to Austin around July 14, 2026
```

<!-- Add your screenshot of proof 03 here -->

### 4. It holds under buried corrections — [`proof/04_buried_corrections.py`](proof/04_buried_corrections.py)

The paper's real scenario: a fact corrected, then **buried under 8 distractor turns**, then queried. Three independent fact types:

```
Scenario: Where does the user live?          current 'austin' present: True   PASS
Scenario: What car does the user drive?      current 'kia' present: True      PASS
Scenario: What is the user's favorite drink? current 'tea' present: True      PASS

3/3 scenarios passed — holds up under buried corrections.
```

<!-- Add your screenshot of proof 04 here -->

---

## How it works

`mem0-recency` wraps your Mem0 object and only changes `add()`:

1. Mem0 stores the new fact as usual.
2. The wrapper searches existing memories (same user) for candidates.
3. For each candidate, an LLM-based detector asks: *does the new fact replace this one for the same attribute of the same subject?*
4. If yes — and only if it's a genuinely older, non-duplicate fact, and removing it won't empty the store — the stale memory is deleted.

Every other Mem0 method (`search`, `get_all`, `delete`, …) passes straight through unchanged.

**Safety guarantees** (all enforced in [`mem0_recency/wrapper.py`](mem0_recency/wrapper.py) and covered by the proofs):

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

python proof/01_does_mem0_fail.py       # shows Mem0 keeps stale facts
python proof/02_detector_works.py       # 10/10 detector accuracy
python proof/03_wrapper_fixes_it.py     # wrapper removes the stale fact
python proof/04_buried_corrections.py   # holds under buried corrections
```

## Scope and honest limitations

This is a **v0.1 proof of concept**, verified on real open-source Mem0 with real API calls — not a benchmarked, production-hardened library. Specifically:

- The proofs cover **a handful of hand-chosen scenarios**, not a large benchmark. A rigorous claim would need dozens of cases and a head-to-head number (stale-retrieval rate with vs. without the wrapper). That's the roadmap.
- Detection **costs an LLM call** per candidate contradiction. Fine for typical apps; worth noting at high volume.
- Mem0's fact extraction is **non-deterministic** (it's LLM-driven), so the exact stored wording varies between runs. The wrapper is built to be safe across this variance, but it operates on whatever Mem0 produces.
- It acts on `add()` going forward; it does not retroactively clean memories written before you wrapped the object.

If you hit a case where it deletes something it shouldn't, or misses a stale fact, please open an issue with the sequence of `add()` calls — that's exactly the kind of case that improves it.

## Roadmap

- A proper benchmark: stale-retrieval rate on the LongMemEval knowledge-update subset, plain Mem0 vs. wrapped.
- Optional "keep history" mode that moves stale facts to metadata instead of deleting.
- A rules-only detector fallback for offline / zero-cost use.

## Credits

Built on the problem identified in Patel, 2026 ([arXiv:2606.27472](https://arxiv.org/abs/2606.27472)). Wraps [Mem0](https://github.com/mem0ai/mem0). Not affiliated with either.

## License

Apache-2.0
