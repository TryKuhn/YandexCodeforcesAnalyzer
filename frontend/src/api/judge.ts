import {api} from './instance.ts';

export interface JudgeContestProblem {
    letter: string;
    position: number;
    problem_id: number;
    max_points: number;
}

export interface JudgeContest {
    id: number;
    name: string;
    scoring: 'icpc' | 'ioi';
    starts_at: string;
    ends_at: string | null;
    freeze_minutes: number | null;
    problems: JudgeContestProblem[];
}

export interface ScoreboardCell {
    problem_id: number;
    solved: boolean;
    attempts: number;
    score: number;
    solved_at: number | null;
}

export interface ScoreboardRow {
    place: number;
    user_id: number;
    display_name: string;
    is_official: boolean;
    solved: number;
    penalty: number;
    score: number;
    cells: ScoreboardCell[];
}

export interface Scoreboard {
    contest_id: number;
    scoring: 'icpc' | 'ioi';
    problems: {letter: string; problem_id: number}[];
    rows: ScoreboardRow[];
}

export async function listContests(): Promise<JudgeContest[]> {
    const res = await api.get('/judge/contests');
    return res.data;
}

export async function getContest(id: number): Promise<JudgeContest> {
    const res = await api.get(`/judge/contests/${id}`);
    return res.data;
}

export async function getScoreboard(id: number): Promise<Scoreboard> {
    const res = await api.get(`/judge/contests/${id}/scoreboard`);
    return res.data;
}

export interface JudgeSubmissionInfo {
    id: number;
    problem_id: number;
    language: string;
    status: string;
    verdict: string | null;
    score: number | null;
    max_time_ms: number | null;
    max_memory_kb: number | null;
    first_failed_test: number | null;
    created_at: string;
    judged_at: string | null;
}

export async function submitSolution(
    contestId: number,
    problemId: number,
    language: string,
    source: string,
): Promise<JudgeSubmissionInfo> {
    const res = await api.post(`/judge/contests/${contestId}/submissions`, {
        problem_id: problemId,
        language,
        source,
    });
    return res.data;
}

export async function mySubmissions(contestId: number): Promise<JudgeSubmissionInfo[]> {
    const res = await api.get(`/judge/contests/${contestId}/submissions/my`);
    return res.data;
}
