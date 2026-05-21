import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Search, ArrowLeft, RefreshCw } from 'lucide-react';
import { api } from '../api/instance';
import { Pagination } from '../components/Pagination';

export const ContestSubmissions = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [subs, setSubs] = useState<any[]>([]);
    const [search, setSearch] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [page, setPage] = useState(1);
    const [perPage, setPerPage] = useState(50);
    const [pagination, setPagination] = useState({ page: 1, per_page: 50, total: 0, total_pages: 1 });
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(search);
            setPage(1);
        }, 400);
        return () => clearTimeout(timer);
    }, [search]);

    const fetchSubmissions = useCallback(() => {
        setIsLoading(true);
        const params = new URLSearchParams({
            page: String(page),
            per_page: String(perPage),
        });
        if (debouncedSearch.trim()) {
            params.set('search', debouncedSearch.trim());
        }

        api.get(`/contests/${id}/submissions_list?${params}`)
            .then(res => {
                setSubs(res.data.items);
                setPagination(res.data.pagination);
            })
            .finally(() => setIsLoading(false));
    }, [id, page, perPage, debouncedSearch]);

    useEffect(() => {
        fetchSubmissions();
    }, [fetchSubmissions]);

    const handlePerPageChange = (newPerPage: number) => {
        setPerPage(newPerPage);
        setPage(1);
    };

    const getVerdictStyle = (verdict: string, banned?: boolean) => {
        if (banned) return 'text-purple-500';
        switch (verdict) {
            case 'OK': return 'text-green-500';
            case 'PARTIAL': return 'text-yellow-500 dark:text-yellow-400';
            case 'COMPILATION_ERROR':
            case 'CompilationError': return 'text-blue-500 dark:text-blue-400';
            default: return 'text-red-500';
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <button onClick={() => navigate(`/contests/${id}`)}
                        className="flex items-center gap-2 text-slate-500 hover:text-blue-600 font-medium text-sm">
                    <ArrowLeft size={18} /> Назад к обзору
                </button>
                <h1 className="text-lg sm:text-xl font-bold dark:text-white">Посылки #{id}</h1>
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
                {isLoading && (
                    <RefreshCw className="absolute right-4 top-1/2 -translate-y-1/2 animate-spin text-blue-500" size={16} />
                )}
            </div>

            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-100 dark:border-slate-800 overflow-hidden shadow-sm overflow-x-auto">
                <table className="w-full text-sm text-left" style={{minWidth: '560px'}}>
                    <thead className="bg-slate-50 dark:bg-slate-800/50 border-b dark:border-slate-800">
                    <tr>
                        <th className="px-4 py-3 font-bold dark:text-white">ID</th>
                        <th className="px-4 py-3 font-bold dark:text-white hidden sm:table-cell">Время</th>
                        <th className="px-4 py-3 font-bold dark:text-white">Участник</th>
                        <th className="px-4 py-3 font-bold dark:text-white">Задача</th>
                        <th className="px-4 py-3 font-bold dark:text-white hidden md:table-cell">Язык</th>
                        <th className="px-4 py-3 font-bold dark:text-white">Баллы</th>
                        <th className="px-4 py-3 font-bold dark:text-white">Вердикт</th>
                    </tr>
                    </thead>
                    <tbody className={isLoading ? 'opacity-50 transition-opacity' : 'transition-opacity'}>
                    {subs.map(s => (
                        <tr key={s.id} className="border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                            <td className="px-4 py-3">
                                <Link
                                    to={`/contests/${id}/submissions/${s.id}`}
                                    className="font-mono text-[10px] text-blue-500 hover:underline bg-blue-50 dark:bg-blue-900/20 px-2 py-1 rounded"
                                >
                                    #{s.id.split('_').pop()}
                                </Link>
                            </td>
                            <td className="px-4 py-3 text-slate-400 text-[11px] hidden sm:table-cell">
                                {new Date(s.send_time).toLocaleString()}
                            </td>
                            <td className="px-4 py-3 font-bold dark:text-white text-sm">{s.participant_login}</td>
                            <td className="px-4 py-3 text-slate-500 text-sm">{s.task_name}</td>
                            <td className="px-4 py-3 text-xs text-slate-400 hidden md:table-cell">{s.language}</td>
                            <td className="px-4 py-3 font-mono text-blue-600 font-bold">{s.banned ? 0 : s.score}</td>
                            <td className={`px-4 py-3 font-bold text-xs ${getVerdictStyle(s.verdict, s.banned)}`}>
                                {s.banned ? 'BANNED' : s.verdict}
                            </td>
                        </tr>
                    ))}
                    </tbody>
                </table>
                {!isLoading && subs.length === 0 && (
                    <div className="p-12 text-center text-slate-500">Посылок не найдено</div>
                )}
            </div>

            {pagination.total > 0 && (
                <Pagination
                    page={pagination.page}
                    totalPages={pagination.total_pages}
                    total={pagination.total}
                    perPage={perPage}
                    onPageChange={setPage}
                    onPerPageChange={handlePerPageChange}
                />
            )}
        </div>
    );
};
