"""Statement routes. Importing registers them on gpt_router."""
from api.user.gpt.routes.statement import (generate_scoring, refine,
                                           update_examples, update_field)

__all__ = ["refine", "update_field", "generate_scoring", "update_examples"]
