"""
Proof that the detector is trustworthy BEFORE we wire it into Mem0.

Each case has an expected answer. If the detector gets the "coexist" cases
wrong, it would delete facts it shouldn't — worse than doing nothing. So we
check both directions.

Run:  python proof/02_detector_works.py
"""

import os
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

from mem0_recency.detect import ContradictionDetector

# (old_fact, new_fact, expected)  expected True = new makes old stale
CASES = [
    ("User lives in Detroit", "User moved from Detroit to Austin", True),
    ("User lives in Detroit", "User lives in Austin now", True),
    ("User drives a Mazda", "User switched to a Kia", True),
    ("User is vegetarian", "User is no longer vegetarian, eats meat now", True),
    ("Meeting is on Monday", "Meeting got moved to Thursday", True),
    # must be False — these coexist, deleting either is wrong:
    ("User likes hiking", "User likes sushi", False),
    ("User has a dog named Rex", "User has a cat named Milo", False),
    ("User lives in Detroit", "User works at Google", False),
    ("User speaks English", "User is learning Spanish", False),
    ("User's sister is Anna", "User's brother is Tom", False),
]


def main():
    det = ContradictionDetector()
    passed = 0
    for old, new, expected in CASES:
        got = det.contradicts(old, new)
        ok = got == expected
        passed += ok
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] expected={expected!s:5} got={got!s:5}  "
              f"OLD: {old!r}  NEW: {new!r}")
    print(f"\n{passed}/{len(CASES)} correct")
    if passed == len(CASES):
        print(">>> Detector is trustworthy. Proceed to the wrapper.")
    elif passed >= len(CASES) - 1:
        print(">>> Good enough (1 miss). Note which case; proceed with caution.")
    else:
        print(">>> Too many misses. Fix the prompt before building the wrapper.")


if __name__ == "__main__":
    main()