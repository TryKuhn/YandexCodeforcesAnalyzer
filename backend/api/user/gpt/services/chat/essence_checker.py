"""Detects whether a statement edit changed the problem's essence.

Runs on the cheap ROUTER_MODEL. Returns the set of dependent file types that
must be regenerated when the essence (constraints / I-O format / task / scoring)
changed; an empty list for cosmetic edits.
"""
import json
from typing import Dict

from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.llm.models import ROUTER_MODEL
from api.user.gpt.services.prompts.essence import (SYSTEM_PROMPT,
                                                   build_user_prompt)


async def check(old_statement: Dict, new_statement: Dict) -> dict:
    """Return {"essence_changed": bool, "dependents": list[str], "reason": str}."""
    try:
        result = await llm.ask(
            ROUTER_MODEL,
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_user_prompt(
                        json.dumps(old_statement, ensure_ascii=False),
                        json.dumps(new_statement, ensure_ascii=False),
                    ),
                },
            ],
            json_mode=True,
        )
        return {
            "essence_changed": bool(result.get("essence_changed", False)),
            "dependents": [str(d) for d in result.get("dependents", []) if d],
            "reason": str(result.get("reason", "")),
        }
    except Exception:
        return {"essence_changed": False, "dependents": [], "reason": ""}
