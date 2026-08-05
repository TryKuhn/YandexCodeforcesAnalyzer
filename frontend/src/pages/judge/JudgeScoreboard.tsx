import {useEffect, useState} from 'react';
import {Link, useParams} from 'react-router-dom';
import {
    getContest,
    getScoreboard,
    type JudgeContest,
    type Scoreboard,
    type ScoreboardRow,
} from '../../api/judge.ts';

function cellFor(row: ScoreboardRow, problemId: number) {
    return row.cells.find((c) => c.problem_id === problemId);
}

function IcpcCell({row, problemId}: {row: ScoreboardRow; problemId: number}) {
    const cell = cellFor(row, problemId);
    if (!cell || (!cell.solved && cell.attempts === 0)) {
        return <span className="text-gray-300">·</span>;
    }
    if (cell.solved) {
        return (
            <span className="font-medium text-green-600">
                +{cell.attempts > 0 ? cell.attempts : ''}
                <span className="block text-xs text-gray-500">{cell.solved_at}</span>
            </span>
        );
    }
    return <span className="text-red-500">−{cell.attempts}</span>;
}

function IoiCell({row, problemId}: {row: ScoreboardRow; problemId: number}) {
    const cell = cellFor(row, problemId);
    if (!cell) return <span className="text-gray-300">·</span>;
    const tone =
        cell.score === 0 ? 'text-red-500' : cell.solved ? 'text-green-600' : 'text-amber-600';
    return <span className={`font-medium ${tone}`}>{cell.score}</span>;
}

export function JudgeScoreboard() {
    const {id} = useParams();
    const contestId = Number(id);
    const [contest, setContest] = useState<JudgeContest | null>(null);
    const [board, setBoard] = useState<Scoreboard | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!contestId) return;
        Promise.all([getContest(contestId), getScoreboard(contestId)])
            .then(([c, b]) => {
                setContest(c);
                setBoard(b);
            })
            .catch(() => setError('Не удалось загрузить таблицу'));
    }, [contestId]);

    if (error) return <div className="p-6 text-red-500">{error}</div>;
    if (!contest || !board) return <div className="p-6 text-gray-500">Загрузка…</div>;

    const isIcpc = board.scoring === 'icpc';

    return (
        <div className="p-6">
            <h1 className="mb-1 text-2xl font-semibold">{contest.name}</h1>
            <p className="mb-4 text-sm text-gray-500">
                {isIcpc ? 'Правила ICPC: решённые задачи и штрафное время' : 'Правила IOI: сумма баллов'}
                {' · '}
                <Link to="submit" className="text-violet-600 hover:underline">отправить решение</Link>
            </p>

            <div className="overflow-x-auto">
                <table className="w-full border-collapse text-sm">
                    <thead>
                        <tr className="border-b text-left">
                            <th className="p-2">#</th>
                            <th className="p-2">Участник</th>
                            {isIcpc ? (
                                <>
                                    <th className="p-2 text-center">Решено</th>
                                    <th className="p-2 text-center">Штраф</th>
                                </>
                            ) : (
                                <th className="p-2 text-center">Баллы</th>
                            )}
                            {board.problems.map((p) => (
                                <th key={p.problem_id} className="p-2 text-center">
                                    {p.letter}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {board.rows.map((row) => (
                            <tr
                                key={row.user_id}
                                className={`border-b ${row.is_official ? '' : 'text-gray-400'}`}
                            >
                                <td className="p-2">{row.place || '—'}</td>
                                <td className="p-2">
                                    {row.display_name}
                                    {!row.is_official && (
                                        <span className="ml-2 text-xs">вне зачёта</span>
                                    )}
                                </td>
                                {isIcpc ? (
                                    <>
                                        <td className="p-2 text-center font-medium">{row.solved}</td>
                                        <td className="p-2 text-center">{row.penalty}</td>
                                    </>
                                ) : (
                                    <td className="p-2 text-center font-medium">{row.score}</td>
                                )}
                                {board.problems.map((p) => (
                                    <td key={p.problem_id} className="p-2 text-center">
                                        {isIcpc ? (
                                            <IcpcCell row={row} problemId={p.problem_id}/>
                                        ) : (
                                            <IoiCell row={row} problemId={p.problem_id}/>
                                        )}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {board.rows.length === 0 && (
                <p className="mt-4 text-gray-500">Пока никто не зарегистрирован.</p>
            )}
        </div>
    );
}
