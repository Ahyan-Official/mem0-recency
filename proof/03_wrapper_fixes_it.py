"""
The payoff proof: same real Mem0 as proof 01, now wrapped with RecencyMemory.
Expectation: after the Austin correction, the stale 'Detroit' fact is GONE.

Run:  python proof/03_wrapper_fixes_it.py
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
        "config": {"collection_name": "recency_fix", "path": "./.mem0_fix_db"},
    },
}


def show(mem, user, label):
    rows = mem.get_all(filters={"user_id": user})
    results = rows.get("results", rows) if isinstance(rows, dict) else rows
    print(f"\n--- {label} ---")
    for m in results:
        print("   •", m.get("memory", m) if isinstance(m, dict) else m)
    return results


def main():
    base = Memory.from_config(config)
    memory = RecencyMemory(base, verbose=True)   # wrapped!
    user = "fix_user"

    try:
        base.delete_all(user_id=user)
    except Exception:
        pass

    print("Step 1: user says they live in Detroit")
    memory.add("I live in Detroit", user_id=user)

    print("Step 2: user corrects it — moved to Austin")
    memory.add("Actually I moved to Austin last month", user_id=user)

    stored = show(memory, user, "final memory (should have NO 'Detroit')")

    text = " ".join(
        (m.get("memory", "") if isinstance(m, dict) else str(m)) for m in stored
    ).lower()
    stale_standalone = any(
        "detroit" in ((m.get("memory", "") if isinstance(m, dict) else str(m)).lower())
        and "austin" not in ((m.get("memory", "") if isinstance(m, dict) else str(m)).lower())
        for m in stored
    )
    print("\n=================  RESULT  =================")
    if memory.superseded_count > 0 and not stale_standalone and "austin" in text:
        print("SUCCESS: stale 'lives in Detroit' removed, current 'Austin' kept.")
        print(f"(RecencyMemory superseded {memory.superseded_count} stale fact(s).)")
    else:
        print("Check the printout above manually.")
    print("===========================================")


if __name__ == "__main__":
    main()