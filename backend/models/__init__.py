"""Aggregates all ORM models and re-exports them for convenient importing."""
from models.base import Base
from models.contest.contest import Contest
from models.contest.contest_participant import ContestParticipant
from models.contest.task import Task
from models.contest.task_result import TaskResult
from models.participant.participant import Participant
from models.plagiarism.pair_of_banned_submissions import \
    PairOfBannedSubmissions
from models.plagiarism.plagiarism_report import PlagiarismReport
from models.submissions.submission import Submission
from models.task.checker import PolygonChecker
from models.task.generated_file import TaskGeneratedFile
from models.task.generator import PolygonGenerator
from models.task.problem import PolygonProblem
from models.task.script import PolygonScript
from models.task.session import PipelineStage, TaskSession
from models.task.solution import PolygonSolution
from models.task.statement import PolygonStatement
from models.task.test import PolygonTest
from models.task.test_group import PolygonTestGroup
from models.task.validator import PolygonValidator
from models.user.refresh_token import RefreshToken
from models.user.role import Role
from models.user.user import User

__all__ = [
    "Base",
    "TaskSession",
    "TaskGeneratedFile",
    "PipelineStage",
    "Contest",
    "ContestParticipant",
    "Task",
    "TaskResult",
    "PairOfBannedSubmissions",
    "PlagiarismReport",
    "Submission",
    "Participant",
    "RefreshToken",
    "Role",
    "User",
    "PolygonProblem",
    "PolygonStatement",
    "PolygonChecker",
    "PolygonValidator",
    "PolygonSolution",
    "PolygonTest",
    "PolygonTestGroup",
    "PolygonGenerator",
    "PolygonScript",
]
