"""File routes. Importing registers them on gpt_router."""
from api.user.gpt.routes.files import (add_custom_solution,
                                       delete_custom_solution,
                                       generate_solution, manual_fix,
                                       refine_file)

__all__ = ["refine_file", "manual_fix", "generate_solution",
           "add_custom_solution", "delete_custom_solution"]
