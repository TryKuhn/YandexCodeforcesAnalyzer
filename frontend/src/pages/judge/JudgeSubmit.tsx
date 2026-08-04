import {useEffect, useState} from 'react';
import {useParams} from 'react-router-dom';
import {
    getContest,
    mySubmissions,
    submitSolution,
    type JudgeContest,
    type JudgeSubmissionInfo,
} from '../../api/judge.ts';
import {parseServerDate} from '../../utils/date.ts';

const LANGUAGES = [
    {id: 'cpp', label: 'C++ 17'},
    {id: 'python', label: 'Python 3'},
];

const VERDICT_TONE: Record<string, string> = {
    OK: 'text-green-600',
    WA: 'text-red-500',
    TLE: 'text-amber-600',
    MLE: 'text-amber-600',
    RE: 'text-red-500',
    PE: 'text-amber-600',
    CE: 'text-slate-500',
    XX: 'text-purple-500',
};

function VerdictCell({submission}: {submission: JudgeSubmissionInfo}) {
    if (submission.status !== 'judged') {
        return <span className="text-slate-400">{submission.status === 'running' ? 'проверяется…' : 'в очереди'}</span>;
    }
    const verdict = submission.verdict ?? '—';
    return (
        <span className={VERDICT_TONE[verdict] ?? ''}>
            {verdict}
            {submission.first_failed_test !== null && verdict !== 'OK' && (
                <span className="text-slate-400"> на тесте {submission.first_failed_test}</span>
            )}
        </span>
    );
}

export function JudgeSubmit() {
    const {id} = useParams();
    const contestId = Number(id);
    const [contest, setContest] = useState<JudgeContest | null>(null);
    const [problemId, setProblemId] = useState<number | null>(null);
    const [language, setLanguage] = useState('cpp');
    const [source, setSource] = useState('');
    const [sending, setSending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [submissions, setSubmissions] = useState<JudgeSubmissionInfo[]>([]);

    const refresh = () => mySubmissions(contestId).then(setSubmissions).catch(() => {});

    useEffect(() => {
        if (!contestId) return;
        getContest(contestId)
            .then((c) => {
                setContest(c);
                if (c.problems.length > 0) setProblemId(c.problems[0].problem_id);
            })
            .catch(() => setError('Не удалось загрузить соревнование'));
        refresh();
    }, [contestId]);

    // a queued submission becomes a verdict without the page being reloaded
    useEffect(() => {
        if (!submissions.some((s) => s.status !== 'judged')) return;
        const timer = setInterval(refresh, 3000);
        return () => clearInterval(timer);
    }, [submissions, contestId]);

    const send = async () => {
        if (!problemId || !source.trim()) return;
        setSending(true);
        setError(null);
        try {
            await submitSolution(contestId, problemId, language, source);
            setSource('');
            await refresh();
        } catch {
            setError('Не удалось отправить решение');
        } finally {
            setSending(false);
        }
    };

    if (error && !contest) return <div className="p-6 text-red-500">{error}</div>;
    if (!contest) return <div className="p-6 text-gray-500">Загрузка…</div>;

    return (
        <div className="p-6">
            <h1 className="mb-4 text-2xl font-semibold">{contest.name} — отправка решения</h1>

            <div className="mb-4 flex flex-wrap gap-3">
                <select
                    value={problemId ?? ''}
                    onChange={(e) => setProblemId(Number(e.target.value))}
                    className="rounded-lg border px-3 py-2"
                >
                    {contest.problems.map((p) => (
                        <option key={p.problem_id} value={p.problem_id}>
                            Задача {p.letter}
                        </option>
                    ))}
                </select>
                <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="rounded-lg border px-3 py-2"
                >
                    {LANGUAGES.map((l) => (
                        <option key={l.id} value={l.id}>{l.label}</option>
                    ))}
                </select>
            </div>

            <textarea
                value={source}
                onChange={(e) => setSource(e.target.value)}
                placeholder="Вставь исходный код решения"
                spellCheck={false}
                className="h-64 w-full rounded-lg border p-3 font-mono text-sm"
            />

            {error && <p className="mt-2 text-red-500">{error}</p>}

            <button
                onClick={send}
                disabled={sending || !source.trim() || !problemId}
                className="mt-3 rounded-lg bg-violet-600 px-5 py-2 text-white disabled:opacity-50"
            >
                {sending ? 'Отправка…' : 'Отправить'}
            </button>

            <h2 className="mb-2 mt-8 text-xl font-semibold">Мои посылки</h2>
            {submissions.length === 0 ? (
                <p className="text-gray-500">Пока ни одной посылки.</p>
            ) : (
                <table className="w-full border-collapse text-sm">
                    <thead>
                        <tr className="border-b text-left">
                            <th className="p-2">Время</th>
                            <th className="p-2">Задача</th>
                            <th className="p-2">Язык</th>
                            <th className="p-2">Вердикт</th>
                            <th className="p-2 text-right">Баллы</th>
                            <th className="p-2 text-right">Время</th>
                            <th className="p-2 text-right">Память</th>
                        </tr>
                    </thead>
                    <tbody>
                        {submissions.map((s) => {
                            const slot = contest.problems.find((p) => p.problem_id === s.problem_id);
                            return (
                                <tr key={s.id} className="border-b">
                                    <td className="p-2">{parseServerDate(s.created_at).toLocaleTimeString()}</td>
                                    <td className="p-2">{slot?.letter ?? s.problem_id}</td>
                                    <td className="p-2">{s.language}</td>
                                    <td className="p-2"><VerdictCell submission={s}/></td>
                                    <td className="p-2 text-right">{s.score ?? '—'}</td>
                                    <td className="p-2 text-right">
                                        {s.max_time_ms !== null ? `${s.max_time_ms} мс` : '—'}
                                    </td>
                                    <td className="p-2 text-right">
                                        {s.max_memory_kb !== null ? `${s.max_memory_kb} КБ` : '—'}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            )}
        </div>
    );
}
