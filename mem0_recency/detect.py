"""
Contradiction detector: does a NEW fact make an OLD stored fact stale?

Uses an OpenAI LLM call. It answers ONE narrow question — should the old
memory be removed because the new one replaces its value for the SAME
attribute of the SAME subject? It deliberately says False on facts that can
both be true at once, so we never delete something that should coexist.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional


class ContradictionDetector:
    def __init__(self, model: str = "gpt-4o-mini", client: object = None):
        self._model = model
        self._client = client

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI()  
        return self._client

    def contradicts(self, old_fact: str, new_fact: str) -> bool:
        """Return True if new_fact supersedes/replaces old_fact."""
        prompt = (
            "You maintain a user's long-term memory. A NEW fact has arrived. "
            "Decide whether it makes an OLD stored fact OUTDATED — i.e. the old "
            "fact should be removed because the new one replaces its value for "
            "the SAME attribute of the SAME subject.\n\n"
            "Answer true ONLY if they describe the same attribute and the value "
            "changed (a move, a switch, a correction, a cancellation, an "
            "update). Answer false if BOTH can be true at the same time, or if "
            "they are about different things.\n\n"
            "Examples:\n"
            'OLD: "User lives in Detroit"  NEW: "User moved to Austin"  -> true\n'
            'OLD: "User drives a Mazda"     NEW: "User switched to a Kia" -> true\n'
            'OLD: "User likes hiking"       NEW: "User likes sushi"       -> false\n'
            'OLD: "User has a dog"          NEW: "User has a cat"         -> false\n\n'
            f'OLD: "{old_fact}"\n'
            f'NEW: "{new_fact}"\n\n'
            'Reply with strict JSON only: {"supersedes": true} or {"supersedes": false}'
        )
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=20,
        )
        text = resp.choices[0].message.content.strip()
        text = re.sub(r"^```(json)?|```$", "", text).strip()
        try:
            return bool(json.loads(text).get("supersedes", False))
        except Exception:
            return "true" in text.lower()