"""Statement routes. Importing registers them on gpt_router."""
from api.user.gpt.routes.statement import (approve, generate_samples,
                                           generate_scoring, refine,
                                           suggest_tags, update_examples,
                                           update_field)

__all__ = ["refine", "approve", "update_field", "generate_scoring",
           "generate_samples", "update_examples", "suggest_tags"]
