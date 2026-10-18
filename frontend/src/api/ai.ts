// api/ai.ts — client of the AI authoring service (proxied by the backend at /api/ai).

import { api } from './instance';

export type Role = 'user' | 'assistant' | 'system';

export interface AiMessage {
    id: number;
    role: Role;
    content: string;
    timestamp: string | null;
    is_error: boolean;
    updated_files: string[];
    meta: {
        intent?: string;
        targets?: string[];
        changed?: string[];
        dropped?: string[];
        errors?: string[];
        run_id?: string;
        context?: ChatContext;
        [key: string]: unknown;
    };
}

export interface AiEvent {
    id: number;
    source: 'polygon' | 'ai' | 'build';
    title: string;
    changes: { kind: string; text: string; [key: string]: unknown }[];
    seen: boolean;
    created_at: string | null;
}

export type RunStatus = 'queued' | 'running' | 'done' | 'failed' | 'needs_user' | 'cancelled';
export type RunKind = 'chat' | 'generate' | 'groups' | 'build';

export interface AiRun {
    id: string;
    kind: RunKind;
    status: RunStatus;
    step: string;
    progress_done: number;
    progress_total: number;
    error: string | null;
    result: Record<string, unknown> | null;
    parent_run_id: string | null;
    created_at: string | null;
    started_at: string | null;
    finished_at: string | null;
}

export type BuildState = 'STARTING' | 'PENDING' | 'RUNNING' | 'READY' | 'FAILED' | 'TIMEOUT' | 'ERROR' | 'CANCELLED';

/** States after which Polygon/the service will not change the build any more. */
export const BUILD_FINAL_STATES: BuildState[] = ['READY', 'FAILED', 'TIMEOUT', 'ERROR', 'CANCELLED'];
export const isBuildFinal = (state?: string | null) => !!state && (BUILD_FINAL_STATES as string[]).includes(state);

export interface AiBuild {
    id: number;
    run_id: string | null;
    attempt: number;
    package_id: number | null;
    state: BuildState;
    comment: string;
    created_at: string | null;
    updated_at: string | null;
}

export interface PlanCase { args: string; count: number }

export interface PlanGroup {
    name: string;
    points: number;
    description: string;
    dependencies: string[];
    generator?: string | null;
    cases: PlanCase[];
    samples: boolean;
}

export interface TestPlan {
    use_groups: boolean;
    groups: PlanGroup[];
    note?: string;
}

export interface AiSession {
    session_id: string;
    polygon_id: number;
    problem_type: string;
    model: string;
    auto_build: boolean;
    groups_plan: TestPlan | null;
    last_synced_at: string | null;
    sync_error: string | null;
}

export interface OpenedSession extends AiSession {
    messages: AiMessage[];
    unseen_events: AiEvent[];
    last_event_id: number;
    active_run: AiRun | null;
    latest_build: AiBuild | null;
}

export interface SessionState {
    messages: AiMessage[];
    events: AiEvent[];
    active_run: AiRun | null;
    latest_build: AiBuild | null;
    last_synced_at: string | null;
    sync_error: string | null;
}

export interface ChatContext {
    scope: 'task' | 'statement' | 'file';
    file?: string;
    file_role?: string;
}

export interface AiModel {
    id: string;
    name: string;
    vendor: string;
    price_in: number;
    price_out: number;
    context: number;
}

export interface PlanPreview {
    plan: TestPlan;
    script: string;
    scoring: string;
    tests: number;
    total_points: number;
}

const s = (sessionId: string) => `/ai/sessions/${sessionId}`;

export const aiApi = {
    models: async () => (await api.get<{ default: string; models: AiModel[] }>('/ai/models')).data,

    createProblem: async (body: {
        name: string;
        problem_type: string;
        model?: string;
        idea?: string;
        plan?: TestPlan;
        groups?: boolean;
    }) => (await api.post<{ polygon_id: number; session: AiSession; run: AiRun | null }>('/ai/problems', body)).data,

    open: async (polygonId: number) =>
        (await api.get<OpenedSession>(`/ai/problems/${polygonId}/session`)).data,

    patch: async (sessionId: string, body: { model?: string; problem_type?: string; auto_build?: boolean }) =>
        (await api.patch<AiSession>(s(sessionId), body)).data,

    sync: async (sessionId: string) =>
        (await api.post<{ skipped: boolean; event: AiEvent | null; last_synced_at?: string; sync_error?: string }>(
            `${s(sessionId)}/sync`,
        )).data,

    state: async (sessionId: string, afterMessage: number, afterEvent: number) =>
        (await api.get<SessionState>(`${s(sessionId)}/state`, {
            params: { after_message: afterMessage, after_event: afterEvent },
        })).data,

    send: async (sessionId: string, text: string, context?: ChatContext) =>
        (await api.post<{ message: AiMessage; run: AiRun }>(`${s(sessionId)}/messages`, { text, context })).data,

    generate: async (sessionId: string, body: { idea: string; plan?: TestPlan; groups?: boolean; brute?: boolean }) =>
        (await api.post<{ run: AiRun }>(`${s(sessionId)}/generate`, body)).data,

    plan: async (sessionId: string) =>
        (await api.get<{ plan: TestPlan | null; source: 'saved' | 'polygon' | 'empty' }>(`${s(sessionId)}/plan`)).data,

    previewPlan: async (sessionId: string, plan: TestPlan) =>
        (await api.post<PlanPreview>(`${s(sessionId)}/plan/preview`, { plan })).data,

    applyGroups: async (sessionId: string, body: { plan?: TestPlan; request?: string }) =>
        (await api.post<{ run: AiRun }>(`${s(sessionId)}/groups`, body)).data,

    build: async (sessionId: string) =>
        (await api.post<{ run: AiRun; already: boolean }>(`${s(sessionId)}/build`)).data,

    builds: async (sessionId: string, limit = 20) =>
        (await api.get<AiBuild[]>(`${s(sessionId)}/builds`, { params: { limit } })).data,

    run: async (runId: string) => (await api.get<AiRun>(`/ai/runs/${runId}`)).data,

    cancel: async (runId: string) => (await api.post<AiRun>(`/ai/runs/${runId}/cancel`)).data,

    seen: async (sessionId: string, upTo: number) =>
        (await api.post(`${s(sessionId)}/events/seen`, { up_to: upTo })).data,

    scoring: async (sessionId: string) =>
        (await api.post<{ scoring: string }>(`${s(sessionId)}/scoring`)).data,

    solutionDraft: async (sessionId: string, body: { tag: string; name: string; instruction?: string }) =>
        (await api.post<{ skipped: boolean; code?: string; reason?: string }>(`${s(sessionId)}/solution-draft`, body)).data,
};

export const RUN_LABELS: Record<RunKind, string> = {
    chat: 'Ответ ИИ',
    generate: 'Генерация задачи',
    groups: 'Группы и баллы',
    build: 'Сборка пакета',
};

export const isActive = (run: AiRun | null | undefined) =>
    !!run && (run.status === 'queued' || run.status === 'running');

/** Human-readable error from an axios failure. */
export const errorText = (e: unknown, fallback: string): string => {
    const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
    return typeof detail === 'string' && detail ? detail : fallback;
};
