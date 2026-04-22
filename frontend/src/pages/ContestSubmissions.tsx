import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Search, ArrowLeft } from 'lucide-react';
import { api } from '../api/instance';

export const ContestSubmissions = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [subs, setSubs] = useState<any[]>([]);
    const [search, setSearch] = useState('');

    useEffect(() => {
        api.get(`/contests/${id}/submissions_list`).then(res => setSubs(res.data));
    }, [id]);

    // Функция для определения цвета текста в зависимости от вердикта
    const getVerdictStyle = (verdict: string) => {
        switch (verdict) {
            case 'OK':
                return 'text-green-500';
            case 'PARTIAL':
                return 'text-yellow-500 dark:text-yellow-400';
            case 'COMPILATION_ERROR':
                return 'text-blue-500 dark:text-blue-400';
            case 'CompilationError':
                return 'text-blue-500 dark:text-blue-400';
            default:
                return 'text-red-500';
        }
    };

    const filtered = subs.filter(s =>
        s.participant_login.toLowerCase().includes(search.toLowerCase()) ||
        s.task_name.toLowerCase().includes(search.toLowerCase()) ||
        s.id.includes(search)
    );

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="flex justify-between items-center">
                <button onClick={() => navigate(`/contests/${id}`)} className="flex items-center gap-2 text-slate-500 hover:text-blue-600 font-medium">
                    <ArrowLeft size={20} /> Назад к обзору
                </button>
                <h1 className="text-xl font-bold dark:text-white">Посылки контеста #{id}</h1>
            </div>

            <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                <input
                    type="text"
                    placeholder="Поиск по логину, задаче или ID..."
                    className="w-full bg-white dark:bg-slate-900 dark:text-white rounded-2xl py-3 pl-12 pr-4 outline-none border border-slate-100 dark:border-slate-800 focus:ring-2 focus:ring-blue-500 text-sm"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                />
            </div>

            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-100 dark:border-slate-800 overflow-hidden shadow-sm">
                <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 dark:bg-slate-800/50 border-b dark:border-slate-800">
                    <tr>
                        <th className="px-6 py-4 font-bold dark:text-white">ID</th>
                        <th className="px-6 py-4 font-bold dark:text-white">Время отправки</th>
                        <th className="px-6 py-4 font-bold dark:text-white">Участник</th>
                        <th className="px-6 py-4 font-bold dark:text-white">Задача</th>
                        <th className="px-6 py-4 font-bold dark:text-white">Язык</th>
                        <th className="px-6 py-4 font-bold dark:text-white">Баллы</th>
                        <th className="px-6 py-4 font-bold dark:text-white">Вердикт</th>
                    </tr>
                    </thead>
                    <tbody>
                    {filtered.map(s => (
                        <tr key={s.id} className="border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                            <td className="px-6 py-4">
                                <Link
                                    to={`/contests/${id}/submissions/${s.id}`}
                                    className="font-mono text-[10px] text-blue-500 hover:underline bg-blue-50 dark:bg-blue-900/20 px-2 py-1 rounded"
                                >
                                    #{s.id.split('_').pop()}
                                </Link>
                            </td>
                            <td className="px-6 py-4 text-slate-400 text-[11px]">
                                {new Date(s.send_time).toLocaleString()}
                            </td>
                            <td className="px-6 py-4 font-bold dark:text-white">{s.participant_login}</td>
                            <td className="px-6 py-4 text-slate-500">{s.task_name}</td>
                            <td className="px-6 py-4 text-xs text-slate-400">{s.language}</td>
                            <td className="px-6 py-4 font-mono text-blue-600 font-bold">{s.score}</td>
                            <td className={`px-6 py-4 font-bold ${getVerdictStyle(s.verdict)}`}>
                                {s.verdict}
                            </td>
                        </tr>
                    ))}
                    </tbody>
                </table>
                {filtered.length === 0 && (
                    <div className="p-12 text-center text-slate-500">Посылок не найдено</div>
                )}
            </div>
        </div>
    );
};
