// pages/tasks/components/NlognPublishModal.tsx
//
// "Опубликовать в NlogN": the built package goes into an ejudge contest (the
// same ejudge contest.nlogn.info judges on), and the NlogN problem bound to
// "<ejudge contest>:<ejudge problem>" is created or updated with the statement
// from the package; optionally it is added to an NlogN contest. One backend
// job (nlogn.publish), followed here.

import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, CheckCircle, ExternalLink, Loader2, Search, Send, X } from 'lucide-react';
import { api } from '../../../api/instance';
import { errorText } from '../../../api/ai';

interface Props {
    polygonId: number;
    packageId: number;
    defaultTitle?: string;
    onClose: () => void;
}

interface Publication {
    ejudge_contest_id: number;
    ejudge_problem_id: number;
    short_name: string;
    title: string;
    nlogn_problem_id: number | null;
    nlogn_contest_id: number | null;
    nlogn_problem_url: string | null;
}

interface Status {
    nlogn: { linked: boolean; base_url?: string; username?: string; full_name?: string };
    ejudge: { configured: boolean; source?: string; error?: string; ssh_host: string | null };
    publication: Publication | null;
}

interface NlognContest { id: number; name: string; problems_count: number; url: string }

interface Result {
    ok: boolean;
    error?: string;
    ejudge_contest_id: number;
    ejudge_problem_id: number;
    short_name: string;
    title: string;
    ejudge_reloaded?: boolean;
    auto_contest?: { id: number; created: boolean } | null;
    warnings?: string[];
    nlogn?: {
        problem_id: number | null;
        created: boolean;
        url: string | null;
        contest: { id: number; name: string; symbolIndex?: string } | null;
    };
}

interface JobState { status: string; progress: number; result: Result | null; error: string | null }

const inputCls = 'w-full text-sm px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 '
    + 'dark:border-slate-700 dark:text-white outline-none focus:ring-2 focus:ring-blue-500';
const labelCls = 'block text-[11px] font-bold text-slate-500 dark:text-slate-400 mb-1';

export const NlognPublishModal = ({ polygonId, packageId, defaultTitle, onClose }: Props) => {
    const [status, setStatus] = useState<Status | null>(null);
    const [contestId, setContestId] = useState('');
    const [shortName, setShortName] = useState('');
    const [title, setTitle] = useState(defaultTitle || '');
    const [nlognContestId, setNlognContestId] = useState('');
    const [nlognContest, setNlognContest] = useState<NlognContest | null>(null);
    const [job, setJob] = useState<JobState | null>(null);
    const [busy, setBusy] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    useEffect(() => {
        api.get<Status>('/nlogn/status', { params: { polygon_id: polygonId } })
            .then(r => {
                setStatus(r.data);
                const last = r.data.publication;
                if (last) {
                    // the same ejudge contest/problem again: NlogN updates the problem instead of a duplicate
                    setContestId(String(last.ejudge_contest_id));
                    setShortName(last.short_name);
                    if (last.title) setTitle(t => t || last.title);
                    if (last.nlogn_contest_id) setNlognContestId(String(last.nlogn_contest_id));
                }
            })
            .catch(e => setError(errorText(e, 'Ошибка')));
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [polygonId]);

    const run = async (label: string, fn: () => Promise<void>) => {
        setBusy(label);
        setError(null);
        try { await fn(); } catch (e) { setError(errorText(e, 'Ошибка')); } finally { setBusy(null); }
    };

    const checkNlognContest = () => run('contest', async () => {
        setNlognContest((await api.get<NlognContest>(`/integrations/nlogn/contests/${Number(nlognContestId)}`)).data);
    });

    const publish = () => run('publish', async () => {
        const { job_id } = (await api.post<{ job_id: string }>('/nlogn/publish', {
            polygon_id: polygonId,
            package_id: packageId,
            // empty: TaskForge picks the contest itself (the previous one or an automatic block)
            ejudge_contest_id: contestId ? Number(contestId) : undefined,
            short_name: shortName.trim() || undefined,
            title: title.trim() || undefined,
            nlogn_contest_id: nlognContestId ? Number(nlognContestId) : undefined,
        })).data;
        setJob({ status: 'queued', progress: 0, result: null, error: null });
        pollRef.current = setInterval(async () => {
            try {
                const state = (await api.get<JobState>(`/nlogn/publish/${job_id}`)).data;
                setJob(state);
                if (state.status === 'done' || state.status === 'failed') {
                    if (pollRef.current) clearInterval(pollRef.current);
                }
            } catch { /* keep polling */ }
        }, 2000);
    });

    const validContest = !contestId || (/^\d{1,6}$/.test(contestId) && Number(contestId) > 0);
    const validNlognContest = !nlognContestId || /^\d{1,9}$/.test(nlognContestId);
    const ready = !!status?.nlogn.linked && !!status?.ejudge.configured;
    const running = !!job && job.status !== 'done' && job.status !== 'failed';
    const result = job?.result;
    const failed = job?.status === 'failed' || result?.ok === false;
    const last = status?.publication;

    return (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
            <div
                className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto p-5 space-y-4"
                onClick={e => e.stopPropagation()}
            >
                <div className="flex items-center gap-2">
                    <Send size={16} className="text-blue-500" />
                    <h2 className="text-sm font-bold text-slate-800 dark:text-white flex-1">
                        Опубликовать пакет #{packageId} в NlogN
                    </h2>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-700"><X size={16} /></button>
                </div>

                <p className="text-xs text-slate-500">
                    Пакет выгружается в контест ejudge, на котором судит NlogN, а в NlogN создаётся (или обновляется)
                    задача с условием из пакета, привязанная к этой задаче ejudge.
                </p>

                {status && !ready && (
                    <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 text-xs space-y-1">
                        {!status.nlogn.linked && <div>NlogN не привязан: войдите в NlogN под администратором.</div>}
                        {!status.ejudge.configured && <div>{status.ejudge.error || 'Не настроен сервер ejudge.'}</div>}
                        <div>
                            Подключите в <Link to="/profile" className="font-bold underline">профиле → Интеграции</Link>
                            {!status.nlogn.linked && !status.ejudge.configured ? ' (NlogN и Ejudge)' : ''}.
                        </div>
                    </div>
                )}
                {ready && (
                    <p className="text-[11px] text-slate-400">
                        NlogN: {status?.nlogn.full_name || status?.nlogn.username} на {status?.nlogn.base_url?.replace(/^https?:\/\//, '')}
                        {' · '}ejudge: {status?.ejudge.ssh_host}
                    </p>
                )}
                {last && (
                    <p className="text-[11px] text-slate-500 bg-slate-50 dark:bg-slate-800/60 rounded-lg p-2">
                        Уже опубликована: контест ejudge {last.ejudge_contest_id}, задача {last.ejudge_problem_id}
                        {' '}({last.short_name})
                        {last.nlogn_problem_url && <>
                            {' · '}<a href={last.nlogn_problem_url} target="_blank" rel="noreferrer" className="text-blue-600 underline">
                                задача NlogN #{last.nlogn_problem_id}
                            </a>
                        </>}
                    </p>
                )}

                <div className="grid grid-cols-2 gap-3">
                    <div>
                        <label className={labelCls}>ID контеста ejudge (необяз.)</label>
                        <input className={inputCls} value={contestId} placeholder="авто" disabled={running}
                               title="Пусто — TaskForge сам выберет контест: прежний для этой задачи или свой блок на 10 задач (создаст новый, когда текущий заполнится)"
                               onChange={e => setContestId(e.target.value.trim())} />
                    </div>
                    <div>
                        <label className={labelCls}>Короткое имя в ejudge (необяз.)</label>
                        <input className={inputCls} value={shortName} placeholder="A" disabled={running}
                               onChange={e => setShortName(e.target.value)} />
                    </div>
                </div>
                {!contestId && (
                    <p className="text-[11px] text-slate-400 -mt-1">
                        Без ID задача попадёт в прежний контест ejudge (если уже публиковалась) или в контест-блок TaskForge
                        на 10 задач; когда блок заполнится, TaskForge сам создаст следующий по образцу.
                    </p>
                )}
                <div>
                    <label className={labelCls}>Название задачи в NlogN</label>
                    <input className={inputCls} value={title} placeholder="по умолчанию — название из условия" disabled={running}
                           onChange={e => setTitle(e.target.value)} />
                </div>
                <div>
                    <label className={labelCls}>Добавить в контест NlogN (необяз., ID)</label>
                    <div className="flex gap-2">
                        <input className={inputCls} value={nlognContestId} placeholder="ID контеста на contest.nlogn.info"
                               disabled={running || !status?.nlogn.linked}
                               onChange={e => { setNlognContestId(e.target.value.trim()); setNlognContest(null); }} />
                        <button onClick={checkNlognContest}
                                disabled={!nlognContestId || !validNlognContest || !!busy || !status?.nlogn.linked}
                                className="flex items-center gap-1 px-3 rounded-lg text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 disabled:opacity-50 shrink-0">
                            {busy === 'contest' ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />} Проверить
                        </button>
                    </div>
                    {nlognContest && (
                        <p className="text-[11px] text-green-600 mt-1">
                            «{nlognContest.name}», задач: {nlognContest.problems_count} —{' '}
                            <a href={nlognContest.url} target="_blank" rel="noreferrer" className="underline">открыть</a>
                        </p>
                    )}
                </div>

                {error && (
                    <div className="p-3 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs flex gap-1.5">
                        <AlertCircle size={14} className="mt-0.5 shrink-0" /> {error}
                    </div>
                )}

                {job && (
                    <div className="space-y-2">
                        {running && (
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                                <Loader2 size={13} className="animate-spin" />
                                {job.status === 'queued' ? 'В очереди…' : `Публикация… ${job.progress}%`}
                            </div>
                        )}
                        {failed && (
                            <div className="p-3 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs">
                                {result?.error || job.error || 'Публикация не удалась'}
                            </div>
                        )}
                        {result?.ok && (
                            <div className="p-3 rounded-xl bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 text-xs space-y-1">
                                <div className="flex items-center gap-1.5 font-bold">
                                    <CheckCircle size={14} /> Опубликовано
                                </div>
                                <div>
                                    ejudge: контест {result.ejudge_contest_id}, задача {result.ejudge_problem_id} ({result.short_name})
                                    {result.ejudge_reloaded ? ', конфигурация перезагружена' : ''}
                                </div>
                                {result.auto_contest && (
                                    <div>
                                        {result.auto_contest.created
                                            ? `Создан новый контест ejudge ${result.auto_contest.id} (блок TaskForge на 10 задач).`
                                            : `Контест ejudge ${result.auto_contest.id} — блок TaskForge для задач NlogN.`}
                                    </div>
                                )}
                                {result.nlogn?.url && (
                                    <div>
                                        NlogN: {result.nlogn.created ? 'создана' : 'обновлена'}{' '}
                                        <a href={result.nlogn.url} target="_blank" rel="noreferrer" className="underline inline-flex items-center gap-0.5">
                                            задача #{result.nlogn.problem_id} <ExternalLink size={10} />
                                        </a>
                                        {result.nlogn.contest && <> · в контесте «{result.nlogn.contest.name}»
                                            {result.nlogn.contest.symbolIndex ? ` под буквой ${result.nlogn.contest.symbolIndex}` : ''}</>}
                                    </div>
                                )}
                                {!!result.warnings?.length && (
                                    <ul className="text-amber-700 dark:text-amber-400 list-disc ml-4">
                                        {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
                                    </ul>
                                )}
                            </div>
                        )}
                    </div>
                )}

                <div className="flex justify-end gap-2">
                    <button onClick={onClose} className="px-4 py-2 rounded-xl text-sm text-slate-500 hover:text-slate-700">
                        {result?.ok ? 'Закрыть' : 'Отмена'}
                    </button>
                    <button onClick={publish} disabled={!ready || !validContest || !validNlognContest || !!busy || running}
                            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-bold bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
                        {busy === 'publish' || running ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                        {result?.ok ? 'Опубликовать ещё раз' : 'Опубликовать'}
                    </button>
                </div>
            </div>
        </div>
    );
};
