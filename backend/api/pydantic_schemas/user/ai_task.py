"""Request/response schemas for the AI-assisted problem-authoring flow."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, field_validator


class ProblemSettings(BaseModel):
    """Problem I/O, limits, tags, and grouping/points toggles."""

    input_file: Optional[str] = "stdin"
    output_file: Optional[str] = "stdout"
    interactive: Optional[bool] = False
    time_limit: Optional[int] = 2000
    memory_limit: Optional[int] = 256
    tags: Optional[List[str]] = []
    enable_groups: Optional[bool] = False
    enable_points: Optional[bool] = False


class UpdateProblemSettingsRequest(BaseModel):
    """Request to update a session's problem settings."""

    session_id: Optional[str] = None
    settings: ProblemSettings


class SuggestTagsRequest(BaseModel):
    """Request to suggest tags for a session's problem."""

    session_id: str


class UpdateExamplesRequest(BaseModel):
    """Request to replace a session's examples.

    Each example is a dict with ``index``, ``input``, and ``output`` keys.
    """

    session_id: str
    examples: List[Dict[str, str]]


class GenerateScoringRequest(BaseModel):
    """Request to generate scoring for a session's problem."""

    session_id: str


class UpdateStatementFieldRequest(BaseModel):
    """Request to set a single statement ``field`` to ``value``."""

    session_id: str
    field: str
    value: str


class ImportFromPolygonFullRequest(BaseModel):
    """Request to import a Polygon problem in full, optionally loading files."""

    polygon_problem_id: int
    model: str
    load_files: Optional[bool] = True


class AIStatementRequest(BaseModel):
    """Request to (re)generate a statement from an idea/prompt and history."""

    idea: Optional[str] = ""
    model: str
    user_prompt: Optional[str] = ""
    history: Optional[List[Dict]] = []


class UpdateSessionSettingsRequest(BaseModel):
    """Request to update a session's model and/or system prompt."""

    model: Optional[str] = None
    system_prompt: Optional[str] = None


class UpdateProblemTypeRequest(BaseModel):
    """Request to set the session's problem type."""

    problem_type: Literal["regular", "interactive", "output_only"]


class AIStatementResponse(BaseModel):
    """Generated statement plus session/stage and optional technical data."""

    statement: Dict[str, Any]
    session_id: str
    stage: str
    technical_data: Optional[Dict[str, Any]] = None


class RefineRequest(BaseModel):
    """Request to refine a statement given feedback and optional settings."""

    session_id: str
    feedback: str
    problem_settings: Optional[Dict] = None


class GenerateFilesResponse(BaseModel):
    """Generated technical files payload plus session/stage."""

    session_id: str
    technical_data: Dict[str, Any]
    stage: str


class RefineFileRequest(BaseModel):
    """Request to refine a single generated file given feedback."""

    session_id: str
    file_key: str
    feedback: str


class ApproveFilesRequest(BaseModel):
    """Request to approve a session's generated files."""

    session_id: str


class PostBuildRefineRequest(BaseModel):
    """Request to refine the problem after build via a chat message."""

    session_id: str
    message: str


class ImportFromPolygonRequest(BaseModel):
    """Request to import a Polygon problem into a new session."""

    polygon_problem_id: int
    model: str


class GenerateSolutionCodeRequest(BaseModel):
    """AI-generate solution code for a user-defined solution (tag + name).

    Unlike ``RefineFileRequest`` (which targets an existing file slot), this
    creates code for an arbitrary custom solution the user is about to add.
    """

    session_id: str
    tag: str
    name: str
    instruction: Optional[str] = None


class ChatContext(BaseModel):
    """Where the user is acting from. ``file`` requires ``file_key``."""
    scope: Literal["task", "statement", "file"] = "task"
    file_key: Optional[str] = None


class ChatRequest(BaseModel):
    """A chat message in a session, scoped by ``context``."""

    session_id: str
    message: str
    context: ChatContext = ChatContext()

    @field_validator("context", mode="before")
    @classmethod
    def _coerce_context(cls, v):
        """Accept the legacy ``context: str`` form so the old frontend keeps
        working: 'statement'/'task' map to that scope, anything else is a file
        key (scope='file')."""
        if isinstance(v, str):
            if v in ("statement", "task"):
                return {"scope": v}
            return {"scope": "file", "file_key": v}
        return v


class ChatResponse(BaseModel):
    """Chat result: an answer or a modification, with any updated artifacts."""

    action: Literal["modify", "answer"]
    response: str
    updated_files: List[str] = []
    synced_to_polygon: bool = False
    statement: Optional[Dict[str, Any]] = None
    technical_data: Optional[Dict[str, Any]] = None
    build_triggered: bool = False
    is_error: bool = False
    # True when a heavy generation was offloaded to a background task: the
    # assistant reply is NOT in this response — the client polls the session
    # chat_log for it (and watches /ai/upload-progress for live stages).
    pending: bool = False


class UploadProgressResponse(BaseModel):
    """Progress/status of an upload-to-Polygon operation."""

    status: str
    stage: str
    current_step: Optional[str] = None
    error: Optional[str] = None
    retries: Optional[int] = None
    technical_data: Optional[Dict] = None
    upload_errors: Optional[Dict] = None
    polygon_problem_id: Optional[int] = None
