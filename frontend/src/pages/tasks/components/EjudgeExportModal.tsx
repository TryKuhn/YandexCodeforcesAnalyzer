// pages/tasks/components/EjudgeExportModal.tsx
//
// Export of a built Polygon package into an ejudge contest: check the contest
// (score system, its problems), preview what will be written (problem.cfg,
// valuer.cfg for olympiad scoring), then run the export job and follow it.

import { useEffect, useRef, useState } from 'react';
import { AlertCircle, CheckCircle, Eye, Loader2, Search, Upload, X } from 'lucide-react';
import { api } from '../../../api/instance';
import { errorText } from '../../../api/ai';

interface Props {
    polygonId: number;
    packageId: number;
    onClose: () => void;
}

interface Status { configured: boolean; web_reload: boolean; url: string | null; ssh_host: string | null }
interface ContestInfo {
    contest_id: number;
    score_system: string;
    advanced_layout: boolean;
    problems: { id: string | null; short_name: string | null; long_name: string | null; internal_name: string | null; extid: string | null }[];
}
interface Report {
    internal_name: string;
    problem_id: number;
    short_name: string;
    score_system: string;
    tests: number;
    groups: { name: string; tests: string; score: number; each_test: boolean; requires: string[]; feedback: string }[];
    renumbered: boolean;
    problem_cfg: string;
    valuer_cfg: string | null;
    warnings: string[];
    reloaded?: boolean;
    problem_dir?: string;
}
interface JobState { status: string; progress: number; result: (Report & { ok: boolean; error?: string }) | null; error: string | null }

const SCORE_SYSTEMS: Record<string, string> = {
    acm: 'ACM (группы и баллы не переносятся)',
    olympiad: 'Олимпиадная (группы → valuer.cfg)',
    kirov: 'Кировская (группы → valuer.cfg)',
    moscow: 'Московская',
};

export const EjudgeExportModal = ({ polygonId, packageId, onClose }: Props) => {
    const [status, setStatus] = useState<Status | null>(null);
    const [contestId, setContestId] = useState('');
    const [shortName, setShortName] = useState('');
    const [contest, setContest] = useState<ContestInfo | null>(null);
    const [preview, setPreview] = useState<Report | null>(null);
    const [job, setJob] = useState<JobState | null>(null);
    const [busy, setBusy] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    useEffect(() => {
        api.get<Status>('/ejudge/status').then(r => setStatus(r.data)).catch(e => setError(errorText(e, 'Ошибка')));
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, []);

    const body = () => ({
        polygon_id: polygonId,
        contest_id: Number(contestId),
        package_id: packageId,
        short_name: shortName.trim() || undefined,
    });

    const run = async (label: string, fn: () => Promise<void>) => {
        setBusy(label);
        setError(null);
        try { await fn(); } catch (e) { setError(errorText(e, 'Ошибка')); } finally { setBusy(null); }
    };

    const checkContest = () => run('contest', async () => {
        setPreview(null);
        setContest((await api.get<ContestInfo>(`/ejudge/contests/${Number(contestId)}`)).data);
    });

    const doPreview = () => run('preview', async () => {
        setPreview((await api.post<Report>('/ejudge/preview', body())).data);
    });

    const doExport = () => run('export', async () => {
        const { job_id } = (await api.post<{ job_id: string }>('/ejudge/export', body())).data;
        setJob({ status: 'queued', progress: 0, result: null, error: null });
        pollRef.current = setInterval(async () => {
            try {
                const state = (await api.get<JobState>(`/ejudge/export/${job_id}`)).data;
                setJob(state);
                if (state.status === 'done' || state.status === 'failed') {
                    if (pollRef.current) clearInterval(pollRef.current);
                }
            } catch { /* keep polling */ }
        }, 2000);
    });

    const validContest = /^\d{1,6}$/.test(contestId) && Number(contestId) > 0;
    const jobDone = job?.status === 'done' || job?.status === 'failed';
    const jobResult = job?.result;

    return (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
            <div
                className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-5 space-y-4"
                onClick={e => e.stopPropagation()}
            >
                <div className="flex items-center gap-2">
                    <Upload size={16} className="text-blue-500" />
                    <h2 className="text-sm font-bold text-slate-800 dark:text-white flex-1">
                        Экспорт пакета #{packageId} в ejudge
                    </h2>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-700"><X size={16} /></button>
                </div>

                {status && !status.configured && (
                    <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 text-xs">
                        Экспорт не настроен на сервере: нужны EJUDGE_SSH_HOST, EJUDGE_JUDGES_DIR, SSH-ключ
                        (и для перезагрузки конфигурации — EJUDGE_URL, EJUDGE_LOGIN, EJUDGE_PASSWORD).
                    </div>
                )}

                <div className="flex flex-wrap items-end gap-2">
                    <div>
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">ID контеста ejudge</label>
                        <input
                            value={contestId}
                            onChange={e => { setContestId(e.target.value.trim()); setContest(null); setPreview(null); }}
                            placeholder="например 1501"
                            className="w-36 text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                        />
                    </div>
                    <div>
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Короткое имя (необяз.)</label>
                        <input
                            value={shortName}
                            onChange={e => { setShortName(e.target.value.trim()); setPreview(null); }}
                            placeholder="A"
                            className="w-24 text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                        />
                    </div>
                    <button
                        onClick={checkContest}
                        disabled={!validContest || !!busy || !status?.configured}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-slate-100 dark:bg-slate-800
                                   text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-50"
                    >
                        {busy === 'contest' ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />}
                        Проверить контест
                    </button>
                    <button
                        onClick={doPreview}
                        disabled={!validContest || !!busy || !status?.configured}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-slate-100 dark:bg-slate-800
                                   text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-50"
                    >
                        {busy === 'preview' ? <Loader2 size={13} className="animate-spin" /> : <Eye size={13} />}
                        Предпросмотр
                    </button>
                </div>

                {error && (
                    <div className="flex items-start gap-2 p-3 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs">
                        <AlertCircle size={14} className="shrink-0 mt-0.5" />
                        <span className="break-words">{error}</span>
                    </div>
                )}

                {contest && (
                    <div className="text-xs space-y-1 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                        <p><b>Система оценки:</b> {SCORE_SYSTEMS[contest.score_system] || contest.score_system}</p>
                        {!contest.advanced_layout && (
                            <p className="text-red-500">В контесте не включён advanced_layout — экспорт невозможен.</p>
                        )}
                        <p><b>Задачи:</b> {contest.problems.length
                            ? contest.problems.map(p => `${p.short_name} (${p.internal_name || p.long_name})`).join(', ')
                            : 'нет'}</p>
                    </div>
                )}

                {preview && (
                    <div className="space-y-2 text-xs">
                        <p>
                            Задача <b>{preview.short_name}</b> (id {preview.problem_id}, каталог <code>{preview.internal_name}</code>),
                            тестов: {preview.tests}, система: {preview.score_system}
                        </p>
                        {preview.groups.length > 0 && (
                            <table className="w-full text-[11px] border border-slate-200 dark:border-slate-700">
                                <thead className="bg-slate-50 dark:bg-slate-800">
                                    <tr>
                                        <th className="p-1">Группа</th><th className="p-1">Тесты</th><th className="p-1">Баллы</th>
                                        <th className="p-1">Требует</th><th className="p-1">Видимость</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {preview.groups.map(g => (
                                        <tr key={g.name} className="text-center border-t border-slate-200 dark:border-slate-700">
                                            <td className="p-1">{g.name}</td><td className="p-1">{g.tests}</td>
                                            <td className="p-1">{g.score}{g.each_test ? ' за тест' : ''}</td>
                                            <td className="p-1">{g.requires.join(', ') || '—'}</td><td className="p-1">{g.feedback}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                        {preview.warnings.length > 0 && (
                            <ul className="text-amber-600 dark:text-amber-400 space-y-0.5">
                                {preview.warnings.map((w, i) => <li key={i}>• {w}</li>)}
                            </ul>
                        )}
                        <details>
                            <summary className="cursor-pointer font-bold text-slate-500">problem.cfg</summary>
                            <pre className="mt-1 p-2 rounded-lg bg-slate-100 dark:bg-slate-950 overflow-x-auto text-[10px]">{preview.problem_cfg}</pre>
                        </details>
                        {preview.valuer_cfg && (
                            <details>
                                <summary className="cursor-pointer font-bold text-slate-500">valuer.cfg</summary>
                                <pre className="mt-1 p-2 rounded-lg bg-slate-100 dark:bg-slate-950 overflow-x-auto text-[10px]">{preview.valuer_cfg}</pre>
                            </details>
                        )}
                        {!job && (
                            <button
                                onClick={doExport}
                                disabled={!!busy}
                                className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-700
                                           text-white disabled:opacity-50 shadow-lg shadow-blue-500/20"
                            >
                                {busy === 'export' ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
                                Экспортировать в ejudge
                            </button>
                        )}
                    </div>
                )}

                {job && (
                    <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-700 text-xs space-y-2">
                        {!jobDone && (
                            <div className="flex items-center gap-2">
                                <Loader2 size={13} className="animate-spin text-blue-500" />
                                <span>Экспорт… {job.progress}%</span>
                            </div>
                        )}
                        {jobDone && jobResult?.ok && (
                            <div className="text-green-600 dark:text-green-400 space-y-1">
                                <p className="flex items-center gap-1.5 font-bold">
                                    <CheckCircle size={14} /> Задача {jobResult.short_name} загружена в контест
                                </p>
                                <p>{jobResult.reloaded ? 'Конфигурация контеста перезагружена.' : 'Перезагрузите конфигурацию контеста вручную.'}</p>
                                {jobResult.warnings?.length > 0 && (
                                    <ul className="text-amber-600 dark:text-amber-400">
                                        {jobResult.warnings.map((w, i) => <li key={i}>• {w}</li>)}
                                    </ul>
                                )}
                            </div>
                        )}
                        {jobDone && !jobResult?.ok && (
                            <p className="text-red-600 dark:text-red-400 break-words">
                                Ошибка экспорта: {jobResult?.error || job.error || 'неизвестная ошибка'}
                            </p>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
