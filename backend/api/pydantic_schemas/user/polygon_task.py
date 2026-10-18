"""Request schemas for the ``/api/polygon`` routes.

Enum-like fields are plain strings: they are normalized and validated against
``api.user.polygon.constants`` by the method wrappers (422 on a bad value).
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class CreatePolygonProblemRequest(BaseModel):
    """Request to create a new Polygon problem with the given name."""

    name: str


class SyncProblemRequest(BaseModel):
    """Empty body for triggering a Polygon problem sync."""

    pass


# --- info / meta -------------------------------------------------------------
class UpdateInfoRequest(BaseModel):
    """Optional problem info/limits fields to update (``None`` = keep)."""

    input_file: Optional[str] = None
    output_file: Optional[str] = None
    interactive: Optional[bool] = None
    well_formed: Optional[bool] = None
    skip_duplicated_tests_validation: Optional[bool] = None
    time_limit: Optional[int] = None
    memory_limit: Optional[int] = None


class UpdateTagsRequest(BaseModel):
    """Replacement list of problem tags."""

    tags: list[str]


class SaveNoteRequest(BaseModel):
    """Problem note (up to 50 chars; empty clears it)."""

    note: str = Field(default="", max_length=50)


class SaveGeneralDescriptionRequest(BaseModel):
    """General problem description text to save."""

    description: str


class SaveGeneralTutorialRequest(BaseModel):
    """General problem tutorial text to save."""

    tutorial: str


class SetAccessRequest(BaseModel):
    """Grant READ / WRITE or revoke (NONE) a user's access to the problem."""

    login: str
    access_type: str


class CommitRequest(BaseModel):
    """Options for committing the working copy."""

    minor_changes: bool = True
    message: Optional[str] = None


# --- statements --------------------------------------------------------------
class SaveStatementRequest(BaseModel):
    """Problem statement fields to save for one language (``None`` = keep)."""

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
    show_in_review: Optional[bool] = None
    show_cautions_and_grammatical_fixes: Optional[bool] = None


# --- files / checking / solutions -------------------------------------------
class SaveFileRequest(BaseModel):
    """A problem file to save; ``type`` is one of resource | source | aux."""

    type: str
    name: str
    content: str
    source_type: Optional[str] = None
    check_existing: Optional[bool] = None
    for_types: Optional[str] = None
    stages: Optional[str] = None
    assets: Optional[str] = None


class SaveSolutionRequest(BaseModel):
    """A solution file to save, with an optional tag and source type."""

    name: str
    content: str
    tag: Optional[str] = None
    source_type: Optional[str] = None
    check_existing: Optional[bool] = None


class EditSolutionExtraTagsRequest(BaseModel):
    """Add (``remove=False``) or remove an extra tag for a testset XOR a group."""

    remove: bool = False
    testset: Optional[str] = None
    test_group: Optional[str] = None
    tag: Optional[str] = None


class SetCheckerRequest(BaseModel):
    """Checker to set: with ``content`` the source is uploaded first; without it
    ``name`` must be an uploaded source or a standard checker (``std::ncmp.cpp``)."""

    name: str
    content: Optional[str] = None


class SetValidatorRequest(BaseModel):
    """Validator file name and content to upload and set on the problem."""

    name: str
    content: str


class SetInteractorRequest(BaseModel):
    """Interactor file name and content to upload and set on the problem."""

    name: str
    content: str


class SaveValidatorTestRequest(BaseModel):
    """Validator test: ``input`` and ``verdict`` are required when adding."""

    test_index: int
    test_input: Optional[str] = None
    test_verdict: Optional[str] = None
    check_existing: Optional[bool] = None
    test_group: Optional[str] = None
    testset: Optional[str] = None


class SaveCheckerTestRequest(BaseModel):
    """Checker test: input/output/answer/verdict are required when adding."""

    test_index: int
    test_input: Optional[str] = None
    test_output: Optional[str] = None
    test_answer: Optional[str] = None
    test_verdict: Optional[str] = None
    check_existing: Optional[bool] = None


# --- scripts / tests / groups -----------------------------------------------
class SaveScriptRequest(BaseModel):
    """Test-generation script source to save."""

    source: str


class UpdateTestRequest(BaseModel):
    """New input for a manual test."""

    test_input: str


class SaveTestRequest(BaseModel):
    """Full ``problem.saveTest`` payload (``test_input=None`` edits metadata only)."""

    test_index: int
    test_input: Optional[str] = None
    check_existing: Optional[bool] = None
    test_group: Optional[str] = None
    test_points: Optional[float] = None
    test_description: Optional[str] = None
    test_use_in_statements: Optional[bool] = None
    test_input_for_statements: Optional[str] = None
    test_output_for_statements: Optional[str] = None
    verify_input_output_for_statements: Optional[bool] = None


class TestIndicesRequest(BaseModel):
    """A non-empty list of test indices."""

    __test__ = False  # not a pytest test class

    test_indices: list[int] = Field(min_length=1)


class SetTestGroupRequest(TestIndicesRequest):
    """Move the given tests into ``test_group``."""

    test_group: str


class SaveTestGroupRequest(BaseModel):
    """Group policies (``None`` = keep current value)."""

    points_policy: Optional[str] = None
    feedback_policy: Optional[str] = None
    dependencies: Optional[list[str]] = None


class EnableGroupsBody(BaseModel):
    """Request body to enable/disable test groups for a testset."""

    enable: bool
    testset: str = "tests"


class EnablePointsBody(BaseModel):
    """Request body to enable/disable per-test points (or checker-percent mode)."""

    enable: bool


# --- packages / materials / issues -------------------------------------------
class BuildPackageRequest(BaseModel):
    """Package build options (defaults keep the old behaviour: full + verify)."""

    full: bool = True
    verify: bool = True
    commit: bool = True


class SaveMaterialRequest(BaseModel):
    """Create/update a material; ``original_name`` renames an existing one."""

    publish_strategy: str
    items: list[dict[str, Any]] = Field(min_length=1)
    original_name: Optional[str] = None


class AddIssueRequest(BaseModel):
    """New issue (Markdown ``content``)."""

    type: str
    content: str = Field(min_length=1, max_length=16384)
    assignee: Optional[str] = None


class UpdateIssueRequest(BaseModel):
    """Issue update: a non-blank comment and/or at least one change."""

    comment: Optional[str] = Field(default=None, max_length=16384)
    status: Optional[str] = None
    type: Optional[str] = None
    assignee: Optional[str] = None
