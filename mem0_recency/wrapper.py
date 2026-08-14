"""
RecencyMemory: wraps a Mem0 Memory so corrected facts don't leave stale
copies behind. Only `add` is changed; every other Mem0 method passes through.

Safety rules (learned the hard way):
  1. Only delete facts that existed BEFORE this add() call. Never delete the
     fact we just added.
  2. Never leave memory empty. If a delete would remove the last fact, skip it.
  3. Skip near-duplicate rephrasings so two versions of the SAME current fact
     don't get treated as a supersession.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .detect import ContradictionDetector


class RecencyMemory:
    def __init__(
        self,
        memory: Any,
        detector: Optional[ContradictionDetector] = None,
        search_limit: int = 10,
        on_supersede: Optional[Callable[[dict, dict], None]] = None,
        verbose: bool = False,
    ):
        self._memory = memory
        self._detector = detector or ContradictionDetector()
        self._search_limit = search_limit
        self._on_supersede = on_supersede
        self._verbose = verbose
        self.superseded_count = 0

    def add(self, messages, *args, **kwargs):
        scope = _scope(kwargs)

        # Snapshot the ids that existed BEFORE this add. Only these are ever
        # eligible for deletion, so we can never delete the just-added fact.
        pre_existing_ids = {m.get("id") for m in self._all(scope) if m.get("id")}

        result = self._memory.add(messages, *args, **kwargs)
        new_memories = _rows(result)
        if not new_memories:
            new_memories = [{"id": None, "memory": _text(messages)}]

        for new in new_memories:
            self._prune(new, scope, pre_existing_ids)
        return result

    def _prune(self, new_memory: dict, scope: dict, eligible_ids: set) -> None:
        new_text = new_memory.get("memory") or new_memory.get("text") or ""
        if not new_text.strip():
            return

        for old in self._search(new_text, scope):
            old_id = old.get("id")
            old_text = old.get("memory") or old.get("text") or ""

            # Rule 1: only delete facts that existed before this add.
            if not old_id or old_id not in eligible_ids:
                continue
            if not old_text or old_id == new_memory.get("id"):
                continue

            # Rule 3: skip near-duplicate rephrasings of the same fact.
            if _near_duplicate(old_text, new_text):
                continue

            # Rule 2: never empty the store — stop if this is the last fact left.
            current = [m for m in self._all(scope) if m.get("id")]
            if len(current) <= 1:
                if self._verbose:
                    print("[recency] skip delete: would empty memory")
                break

            if self._detector.contradicts(old_text, new_text):
                self._memory.delete(memory_id=old_id)
                eligible_ids.discard(old_id)
                self.superseded_count += 1
                if self._on_supersede:
                    self._on_supersede(old, new_memory)
                if self._verbose:
                    print(f"[recency] superseded: {old_text!r} -> {new_text!r}")

    # -- helpers over Mem0's public surface ----------------------------------

    def _all(self, scope: dict) -> list:
        try:
            res = self._memory.get_all(filters=scope)
        except TypeError:
            res = self._memory.get_all(**scope)
        return _rows(res)

    def _search(self, query: str, scope: dict) -> list:
        try:
            res = self._memory.search(query, limit=self._search_limit, filters=scope)
        except TypeError:
            res = self._memory.search(query, limit=self._search_limit, **scope)
        return _rows(res)

    def __getattr__(self, name):
        return getattr(self._memory, name)


def track_updates(memory: Any, **kwargs) -> RecencyMemory:
    return RecencyMemory(memory, **kwargs)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _scope(kwargs: dict) -> dict:
    out = {}
    for k in ("user_id", "agent_id", "run_id", "app_id"):
        if kwargs.get(k) is not None:
            out[k] = kwargs[k]
    return out


def _near_duplicate(a: str, b: str, threshold: float = 0.8) -> bool:
    """True if two facts are mostly the same words (a rephrasing, not a change)."""
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / len(ta | tb)
    return overlap >= threshold


def _rows(result: Any) -> list:
    if result is None:
        return []
    if isinstance(result, dict):
        if isinstance(result.get("results"), list):
            return [m for m in result["results"] if isinstance(m, dict)]
        if "id" in result or "memory" in result or "text" in result:
            return [result]
        return []
    if isinstance(result, list):
        return [m for m in result if isinstance(m, dict)]
    return []


def _text(messages: Any) -> str:
    if isinstance(messages, str):
        return messages
    if isinstance(messages, list):
        parts = []
        for m in messages:
            parts.append(str(m.get("content", m)) if isinstance(m, dict) else str(m))
        return " ".join(parts)
    return str(messages)