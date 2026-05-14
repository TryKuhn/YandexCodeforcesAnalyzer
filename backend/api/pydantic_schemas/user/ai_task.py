from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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


class RefineRequest(BaseModel):
    session_id: str
    feedback: str


class ApproveStatementRequest(BaseModel):
    """Пользователь одобряет условие → запускаем генерацию файлов"""

    session_id: str


class GenerateFilesResponse(BaseModel):
    session_id: str
    technical_data: Dict[str, Any]
    stage: str


class RefineFileRequest(BaseModel):
    """Правка конкретного файла"""

    session_id: str
    file_key: str  # 'validator', 'generator', etc.
    feedback: str  # что именно поправить


class ApproveFilesRequest(BaseModel):
    """Пользователь одобряет файлы → запускаем загрузку"""

    session_id: str


class ManualFixRequest(BaseModel):
    """Пользователь вручную правит файл с ошибкой"""

    session_id: str
    file_key: str
    new_content: str


class PostBuildRefineRequest(BaseModel):
    session_id: str
    message: str


class ImportFromPolygonRequest(BaseModel):
    polygon_problem_id: int
    model: str


class UploadProgressResponse(BaseModel):
    status: str
    stage: str
    current_step: Optional[str] = None
    error: Optional[str] = None
    retries: Optional[int] = None
    technical_data: Optional[Dict] = None
    upload_errors: Optional[Dict] = None
    polygon_problem_id: Optional[int] = None
