"""
Root conftest.py — sets up dummy environment variables and mocks external
C++ extensions so that the app can be imported without a real .env file.
The actual database connection is overridden in test_base.py to use SQLite.
"""
import sys
import types
import os
from typing import Any

import api.crypt.crypt_password as _crypt_mod
from passlib.context import CryptContext

# Ensure the backend directory itself is importable regardless of where
# pytest is invoked from (project root, backend/, IDE, etc.)
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Mock the plagiarism_cpp C++ extension which is not available in test environments
_mock_plagiarism: Any = types.ModuleType("plagiarism_cpp")

class _ProgrammingLanguage:
    Cpp = "cpp"
    Python = "python"

_mock_plagiarism.ProgrammingLanguage = _ProgrammingLanguage

class _Submission:
    def __init__(self):
        self.id = ""
        self.language = _ProgrammingLanguage.Cpp
        self.rawCode = ""
        self.participant = ""
        self.problem = ""

_mock_plagiarism.Submission = _Submission
_mock_plagiarism.compute_similarity_pairs = lambda submissions, threshold: []

sys.modules["plagiarism_cpp"] = _mock_plagiarism

os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")

# Use minimal bcrypt rounds so password hashing doesn't dominate test runtime
_crypt_mod.pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=4)
os.environ.setdefault("YANDEX_CLIENT_ID", "test-yandex-client-id")
os.environ.setdefault("YANDEX_CLIENT_SECRET", "test-yandex-client-secret")
os.environ.setdefault("CF_CLIENT_ID", "test-cf-client-id")
os.environ.setdefault("CF_CLIENT_SECRET", "test-cf-client-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("POSTGRES_DB", "test_db")
os.environ.setdefault("POSTGRES_USER", "test_user")
os.environ.setdefault("POSTGRES_PASSWORD", "test_password")
