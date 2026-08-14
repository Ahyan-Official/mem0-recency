"""
HARD-CASE PROOF: corrections buried in a long conversation.

This mirrors the paper's real scenario (Patel 2026): a fact is stated, then
corrected, then buried under many distractor turns, then queried. This is
where Mem0's additive memory fails hardest — stale facts survive and get
retrieved. We test whether the wrapper keeps the CURRENT value on top.

We run several independent scenarios and score how many end with the current
fact retrievable and the stale one gone.

Run:  python proof/04_buried_corrections.py
Cost: several dollars of API calls (many add/detector calls). Not free.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_dotenv(path=".env"):
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

from mem0 import Memory
from mem0_recency import RecencyMemory

config = {
    "llm": {"provider": "openai", "config": {"model": "gpt-4o-mini", "temperature": 0.0}},
    "embedder": {"provider": "openai", "config": {"model": "text-embedding-3-small"}},
    "vector_store": {
        "provider": "chroma",
        "config": {"collection_name": "recency_hard", "path": "./.mem0_hard_db"},
    },
}

DISTRACTORS = [
    "I love hiking on weekends",
    "My favorite food is pizza",
    "I work as a software engineer",
    "I have a dog named Rex",
    "I'm learning to play guitar",
    "I usually drink coffee in the morning",
    "I enjoy watching sci-fi movies",
    "I went to Italy last summer",
]

# Each scenario: initial fact, correction, the query, current value, stale value.
SCENARIOS = [
    {
        "initial": "I live in Detroit",
        "correction": "I moved to Austin",
        "query": "Where does the user live?",
        "current": "austin",
        "stale": "detroit",
    },
    {
        "initial": "I drive a Mazda",
        "correction": "I sold the Mazda and now drive a Kia",
        "query": "What car does the user drive?",
        "current": "kia",
        "stale": "mazda",
    },
    {
        "initial": "My favorite drink is Coke",
        "correction": "I quit soda, my favorite drink is now green tea",
        "query": "What is the user's favorite drink?",
        "current": "tea",
        "stale": "coke",
    },
]


def run_scenario(memory, base, user, sc):
    try:
        base.delete_all(user_id=user)
    except Exception:
        pass

    # 1. state the initial fact
    memory.add(sc["initial"], user_id=user)
    # 2. correct it
    memory.add(sc["correction"], user_id=user)
    # 3. bury it under distractors
    for d in DISTRACTORS:
        memory.add(d, user_id=user)

    # 4. query — what would the agent retrieve?
    res = memory.search(sc["query"], filters={"user_id": user})
    hits = res.get("results", res) if isinstance(res, dict) else res
    retrieved = " ".join(
        (m.get("memory", "") if isinstance(m, dict) else str(m)) for m in hits
    ).lower()

    has_current = sc["current"] in retrieved
    has_stale = sc["stale"] in retrieved and sc["current"] not in retrieved
    # (has_stale = stale value present in a memory that's NOT the corrected one)

    ok = has_current and not any(
        sc["stale"] in ((m.get("memory", "") if isinstance(m, dict) else str(m)).lower())
        and sc["current"] not in ((m.get("memory", "") if isinstance(m, dict) else str(m)).lower())
        for m in hits
    )
    print(f"\nScenario: {sc['query']}")
    print(f"  retrieved: {retrieved[:200]}")
    print(f"  current '{sc['current']}' present: {has_current}")
    print(f"  result: {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    base = Memory.from_config(config)
    memory = RecencyMemory(base, verbose=True)

    passed = 0
    for i, sc in enumerate(SCENARIOS):
        if run_scenario(memory, base, f"hard_user_{i}", sc):
            passed += 1

    print(f"\n=================  HARD-CASE RESULT  =================")
    print(f"{passed}/{len(SCENARIOS)} scenarios passed")
    if passed == len(SCENARIOS):
        print(">>> Holds up under buried corrections. This is publishable.")
    elif passed >= 1:
        print(">>> Partial. Works sometimes; note which scenarios failed and why.")
    else:
        print(">>> Fails under burial. The single-case demo was not enough.")
    print("=====================================================")


if __name__ == "__main__":
    main()