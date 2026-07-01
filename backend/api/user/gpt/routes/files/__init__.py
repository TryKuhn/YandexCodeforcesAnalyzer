"""File routes. Importing registers them on gpt_router."""
from api.user.gpt.routes.files import (delete_custom_solution,
                                       generate_solution,
                                       generate_solution_code, refine_file)

__all__ = ["refine_file", "generate_solution", "generate_solution_code",
           "delete_custom_solution"]
