"""Request schemas for Polygon problem creation and editing."""
from typing import Optional
from pydantic import BaseModel


class CreatePolygonProblemRequest(BaseModel):
    """Request to create a new Polygon problem with the given name."""

    name: str


class SyncProblemRequest(BaseModel):
    """Empty body for triggering a Polygon problem sync."""

    pass


class SaveStatementRequest(BaseModel):
    """Problem statement fields to save for one language."""

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
    """Optional problem info/limits fields to update."""

    input_file: Optional[str] = None
    output_file: Optional[str] = None
    interactive: Optional[bool] = None
    well_formed: Optional[bool] = None
    time_limit: Optional[int] = None
    memory_limit: Optional[int] = None


class SaveFileRequest(BaseModel):
    """A problem file to save; ``type`` is one of resource | source | aux."""

    type: str
    name: str
    content: str
    source_type: Optional[str] = None
    check_existing: Optional[bool] = None


class SaveSolutionRequest(BaseModel):
    """A solution file to save, with an optional tag and source type."""

    name: str
    content: str
    tag: Optional[str] = None
    source_type: Optional[str] = None


class UpdateTestRequest(BaseModel):
    """New input for a manual test."""

    test_input: str


class SaveScriptRequest(BaseModel):
    """Test-generation script source to save."""

    source: str


class UpdateTagsRequest(BaseModel):
    """Replacement list of problem tags."""

    tags: list[str]


class SetCheckerRequest(BaseModel):
    """Checker file name and content to set on the problem."""

    name: str
    content: str


class SetValidatorRequest(BaseModel):
    """Validator file name and content to set on the problem."""

    name: str
    content: str


class SetInteractorRequest(BaseModel):
    """Interactor file name and content to set on the problem."""

    name: str
    content: str


class SaveGeneralDescriptionRequest(BaseModel):
    """General problem description text to save."""

    description: str


class SaveGeneralTutorialRequest(BaseModel):
    """General problem tutorial text to save."""

    tutorial: str
