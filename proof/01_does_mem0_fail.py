"""
GO / NO-GO PROOF.

Question: when a user corrects a fact, does REAL open-source Mem0 keep the
stale value or overwrite it?

  - Mem0 already overwrites correctly  -> the add-on is pointless. STOP.
  - Mem0 keeps the stale "Detroit"     -> the gap is real. BUILD.

Run:   python proof/01_does_mem0_fail.py
Needs: OPENAI_API_KEY in a .env file (loaded below, no extra dependency).
Cost:  a few cents of OpenAI usage.
"""

import os


def _load_dotenv(path=".env"):
    """Tiny .env loader so we don't need python-dotenv."""
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

if not os.environ.get("OPENAI_API_KEY"):
    raise SystemExit("Set OPENAI_API_KEY in a .env file first.")

from mem0 import Memory

# Default Mem0 config uses OpenAI for both LLM and embeddings. We pin small,
# cheap models and a local Chroma store so the proof is fast and self-contained.
config = {
    "llm": {
        "provider": "openai",
        "config": {"model": "gpt-4o-mini", "temperature": 0.0},
    },
    "embedder": {
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"},
    },
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": "recency_proof",
            "path": "./.mem0_proof_db",
        },
    },
}


def show(memory, user, label):
    rows = memory.get_all(filters={"user_id": user})
    results = rows.get("results", rows) if isinstance(rows, dict) else rows
    print(f"\n--- {label}: Mem0 currently stores ---")
    for m in results:
        print("   •", m.get("memory", m) if isinstance(m, dict) else m)
    return results


def main():
    memory = Memory.from_config(config)
    user = "proof_user"

    # Clean slate so re-runs are honest.
    try:
        memory.delete_all(user_id=user)
    except Exception:
        pass

    print("Step 1: user says they live in Detroit")
    memory.add("I live in Detroit", user_id=user)
    show(memory, user, "after Detroit")

    print("\nStep 2: user corrects it — they moved to Austin")
    memory.add("Actually I moved to Austin last month", user_id=user)
    stored = show(memory, user, "after Austin correction")

    # --- the verdict --------------------------------------------------------
    texts = " ".join(
        (m.get("memory", "") if isinstance(m, dict) else str(m)) for m in stored
    ).lower()
    has_austin = "austin" in texts
    has_detroit = "detroit" in texts

    print("\n=================  VERDICT  =================")
    if has_detroit and has_austin:
        print("Mem0 kept BOTH Detroit and Austin.")
        print(">>> The gap is REAL. Stale 'Detroit' can resurface. BUILD the add-on.")
    elif has_austin and not has_detroit:
        print("Mem0 already replaced Detroit with Austin on its own.")
        print(">>> Gap NOT reproduced here. STOP and rethink before building.")
    else:
        print("Unexpected state — inspect the printout above manually.")
    print("============================================")

    print("\nWhat the agent would retrieve for 'where does the user live?':")
    res = memory.search("where does the user live?", filters={"user_id": user})
    hits = res.get("results", res) if isinstance(res, dict) else res
    for m in hits:
        print("   •", m.get("memory", m) if isinstance(m, dict) else m)

        
if __name__ == "__main__":
    main()