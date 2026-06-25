"""File routes. Importing registers them on gpt_router."""
from api.user.gpt.routes.files import (delete_custom_solution,
                                       generate_solution, refine_file)

__all__ = ["refine_file", "generate_solution", "delete_custom_solution"]
