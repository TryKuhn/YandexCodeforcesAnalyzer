from typing import Optional
from pydantic import BaseModel


class CreatePolygonProblemRequest(BaseModel):
    name: str


class SyncProblemRequest(BaseModel):
    pass


class SaveStatementRequest(BaseModel):
    lang: str = "russian"
    name: str
    legend: str = ""
    input: str = ""
    output: str = ""
    scoring: Optional[str] = None
    interaction: Optional[str] = None
    notes: Optional[str] = None
    tutorial: Optional[str] = None
    encoding: str = "utf-8"


class UpdateInfoRequest(BaseModel):
    input_file: Optional[str] = None
    output_file: Optional[str] = None
    interactive: Optional[bool] = None
    well_formed: Optional[bool] = None
    time_limit: Optional[int] = None
    memory_limit: Optional[int] = None


class SaveFileRequest(BaseModel):
    type: str           # resource | source | aux
    name: str
    content: str
    source_type: Optional[str] = None
    check_existing: Optional[bool] = None


class SaveSolutionRequest(BaseModel):
    name: str
    content: str
    tag: Optional[str] = None
    source_type: Optional[str] = None


class UpdateTestRequest(BaseModel):
    test_input: str     # only for manual tests


class SaveScriptRequest(BaseModel):
    source: str


class UpdateTagsRequest(BaseModel):
    tags: list[str]


class SetCheckerRequest(BaseModel):
    name: str
    content: str


class SetValidatorRequest(BaseModel):
    name: str
    content: str


class SetInteractorRequest(BaseModel):
    name: str
    content: str


class SaveGeneralDescriptionRequest(BaseModel):
    description: str


class SaveGeneralTutorialRequest(BaseModel):
    tutorial: str
