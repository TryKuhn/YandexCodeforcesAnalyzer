// Single source of truth for the user-selectable AI models on the frontend.
// Keep in sync with MAIN_MODELS in services/ai-authoring/authoring/llm/models.py
// (the service also serves the list at GET /api/ai/models).
export const AI_MODELS = [
    { id: 'anthropic/claude-opus-5.5',   name: 'Claude Opus 5.5' },
    { id: 'anthropic/claude-sonnet-5.5', name: 'Claude Sonnet 5.5' },
    { id: 'openai/gpt-6.1-sol',          name: 'GPT-6.1 Sol' },
];

export const DEFAULT_AI_MODEL = 'anthropic/claude-opus-5.5';
