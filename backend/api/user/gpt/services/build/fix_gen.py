"""Code-fixing generation for build/upload error repair."""
import json
from typing import Dict, List

from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.prompts.fix import build_system_prompt


async def fix(
    component: str,
    code: str,
    error: str,
    statement: Dict,
    model: str,
    previous_errors: List[str] | None = None,
    related_files: Dict[str, str] | None = None,
) -> str:
    """Return corrected code for a single broken file.

    ``related_files`` ({file_type: content}) is read-only companion context — e.g.
    the test-generation script when fixing the generator (and vice versa) — so the
    fixer can reconcile shared opt parameters (avoids testlib 'unused key').
    """
    system = build_system_prompt(component, error, previous_errors, related_files)
    parts = [f"Statement:\n{json.dumps(statement, ensure_ascii=False)}"]
    for name, content in (related_files or {}).items():
        if content:
            parts.append(
                f"Related file '{name}' (read-only context, DO NOT rewrite it; "
                f"make '{component}' consistent with it):\n{content}"
            )
    parts.append(f"Broken {component} code (fix THIS file):\n{code}")
    user = "\n\n".join(parts)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return (await llm.ask_text(model, messages)).strip()
