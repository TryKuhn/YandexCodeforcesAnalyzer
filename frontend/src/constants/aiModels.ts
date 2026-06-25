// Single source of truth for the user-selectable AI models.
// Keep in sync with backend MAIN_MODELS (backend/api/user/gpt/services/llm/models.py).
export const AI_MODELS = [
    { id: 'anthropic/claude-opus-4.8',     name: 'Claude Opus 4.8' },
    { id: 'anthropic/claude-sonnet-4.6',   name: 'Claude Sonnet 4.6' },
    { id: 'anthropic/claude-haiku-4.5',    name: 'Claude Haiku 4.5' },
    { id: 'google/gemini-3.1-pro-preview', name: 'Gemini 3.1 Pro' },
    { id: 'openai/gpt-5.5-pro',            name: 'GPT-5.5 Pro' },
];
