import {useEffect, useState} from 'react';
import {Link} from 'react-router-dom';
import {listContests, type JudgeContest} from '../../api/judge.ts';
import {parseServerDate} from '../../utils/date.ts';

export function JudgeContests() {
    const [contests, setContests] = useState<JudgeContest[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        listContests()
            .then(setContests)
            .catch(() => setError('Не удалось загрузить список соревнований'))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div className="p-6 text-gray-500">Загрузка…</div>;
    if (error) return <div className="p-6 text-red-500">{error}</div>;

    return (
        <div className="p-6">
            <h1 className="mb-4 text-2xl font-semibold">Соревнования</h1>
            {contests.length === 0 ? (
                <p className="text-gray-500">Пока ни одного соревнования.</p>
            ) : (
                <ul className="space-y-2">
                    {contests.map((contest) => (
                        <li key={contest.id} className="rounded-lg border p-4">
                            <Link
                                to={`/contests/${contest.id}`}
                                className="text-lg font-medium hover:underline"
                            >
                                {contest.name}
                            </Link>
                            <div className="mt-1 text-sm text-gray-500">
                                {contest.scoring === 'icpc' ? 'Правила ICPC' : 'Правила IOI'}
                                {' · '}
                                задач: {contest.problems.length}
                                {' · '}
                                начало: {parseServerDate(contest.starts_at)?.toLocaleString() ?? '—'}
                            </div>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
