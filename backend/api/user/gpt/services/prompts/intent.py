"""Prompt for the unified intent classifier (cheap router model).

Classifies a chat message into one concrete action so the dispatcher does not
rely on keyword heuristics. The model also picks the target file for an
``edit_file`` action from the files actually present in the session.
"""

ACTIONS = (
    "answer",
    "edit_statement",
    "edit_file",
    "edit_test",
    "build",
    "regenerate",
    "edit_task",
)

SYSTEM_PROMPT = (
    "You route a user's message inside a competitive-programming problem editor "
    "to ONE action. Return ONLY JSON: "
    '{"action": <one of the actions>, "file_key": <file_type or null>}\n\n'
    "Actions:\n"
    '- "answer": the user asks a question, wants an explanation, analysis or '
    "advice — nothing should be changed.\n"
    '- "edit_statement": change the statement text (legend/input/output/notes), '
    "limits, scoring or interaction section.\n"
    '- "edit_file": change ONE specific source file. Set file_key to that file '
    "(pick from the available files).\n"
    '- "edit_test": change tests, the test-generation script, or the sample '
    "tests.\n"
    '- "build": build / rebuild the Polygon package.\n'
    '- "regenerate": recreate the ENTIRE task from scratch (e.g. "переделай '
    'задачу полностью", "сделай задачу заново", a brand-new problem description).\n'
    '- "edit_task": a change touching several files or the whole problem that is '
    "not a full regeneration.\n\n"
    "Rules:\n"
    "- If the user is currently viewing a specific file and asks to change "
    'something, prefer "edit_file" with that file.\n'
    "- Only choose a file_key that appears in the available files; otherwise use "
    "null and a non-file action.\n"
    "- Off-topic messages → \"answer\".\n"
    "- Be decisive; when genuinely unsure between asking and changing, prefer "
    '"answer".'
)


def build_user_prompt(message: str, context_hint: str, available_files: list[str]) -> str:
    """Build the user prompt with the message, current view hint and available files."""
    files = ", ".join(available_files) if available_files else "(none yet)"
    return (
        f"User is currently viewing: {context_hint}.\n"
        f"Available files in this task: {files}.\n"
        f'User message: "{message}"'
    )
