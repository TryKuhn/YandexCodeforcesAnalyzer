from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ProblemSettings(BaseModel):
    input_file: Optional[str] = "stdin"
    output_file: Optional[str] = "stdout"
    interactive: Optional[bool] = False
    time_limit: Optional[int] = 2000
    memory_limit: Optional[int] = 256
    tags: Optional[List[str]] = []
    enable_groups: Optional[bool] = False
    enable_points: Optional[bool] = False


class AddCustomSolutionRequest(BaseModel):
    session_id: str
    tag: str
    name: str


class UpdateProblemSettingsRequest(BaseModel):
    session_id: Optional[str] = None
    settings: ProblemSettings


class GenerateSamplesRequest(BaseModel):
    session_id: str
    count: Optional[int] = 3


class SuggestTagsRequest(BaseModel):
    session_id: str


class UpdateExamplesRequest(BaseModel):
    session_id: str
    examples: List[Dict[str, str]]  # [{index, input, output}]


class GenerateScoringRequest(BaseModel):
    session_id: str


class UpdateStatementFieldRequest(BaseModel):
    session_id: str
    field: str
    value: str


class ImportFromPolygonFullRequest(BaseModel):
    polygon_problem_id: int
    model: str
    load_files: Optional[bool] = True


class AIStatementRequest(BaseModel):
    idea: Optional[str] = ""
    model: str
    user_prompt: Optional[str] = ""
    history: Optional[List[Dict]] = []


class UpdateSessionSettingsRequest(BaseModel):
    model: Optional[str] = None
    system_prompt: Optional[str] = None


class AIStatementResponse(BaseModel):
    statement: Dict[str, Any]
    session_id: str
    stage: str
    technical_data: Optional[Dict[str, Any]] = None


class RefineRequest(BaseModel):
    session_id: str
    feedback: str
    problem_settings: Optional[Dict] = None


class ApproveStatementRequest(BaseModel):
    session_id: str
    problem_settings: Optional[Dict] = None


class GenerateFilesResponse(BaseModel):
    session_id: str
    technical_data: Dict[str, Any]
    stage: str


class RefineFileRequest(BaseModel):
    session_id: str
    file_key: str
    feedback: str


class ApproveFilesRequest(BaseModel):
    session_id: str


class ManualFixRequest(BaseModel):
    session_id: str
    file_key: str
    new_content: str


class PostBuildRefineRequest(BaseModel):
    session_id: str
    message: str


class ImportFromPolygonRequest(BaseModel):
    polygon_problem_id: int
    model: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: str


class UploadProgressResponse(BaseModel):
    status: str
    stage: str
    current_step: Optional[str] = None
    error: Optional[str] = None
    retries: Optional[int] = None
    technical_data: Optional[Dict] = None
    upload_errors: Optional[Dict] = None
    polygon_problem_id: Optional[int] = None
