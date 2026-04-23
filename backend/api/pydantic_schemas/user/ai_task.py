from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class StatementData(BaseModel):
    name: str
    legend: str
    input: str
    output: str
    notes: Optional[str] = None
    tutorial: Optional[str] = None

class AIStatementRequest(BaseModel):
    idea: str
    history: Optional[List[Dict[str, str]]] = None

class AIStatementResponse(BaseModel):
    statement: StatementData
    session_id: str

class RefineRequest(BaseModel):
    session_id: str
    feedback: str

class ApproveUploadRequest(BaseModel):
    session_id: str
    problem_id: int
    user_id: int

class UploadProgressResponse(BaseModel):
    status: str
    current_step: Optional[str] = None
    error: Optional[str] = None
    retries: Optional[int] = None
    tech_data: Optional[Dict[str, Any]] = None
