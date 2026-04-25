import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Clock, Search } from 'lucide-react';
import { api } from '../api/instance';
import { Pagination } from '../components/Pagination';

export const ContestViewPage = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [data, setData] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [perPage, setPerPage] = useState(50);
    const [search, setSearch] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [pagination, setPagination] = useState({ page: 1, per_page: 50, total: 0, total_pages: 1 });

    // Debounce
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(search);
            setPage(1);
        }, 400);
        return () => clearTimeout(timer);
    }, [search]);

    const fetchData = useCallback(() => {
        setIsLoading(true);
        const params = new URLSearchParams({
            page: String(page),
            per_page: String(perPage),
        });
        if (debouncedSearch.trim()) {
            params.set('search', debouncedSearch.trim());
        }

        api.get(`/contests/${id}/table?${params}`)
            .then(res => {
                setData(res.data);
                setPagination(res.data.pagination);
            })
            .catch(err => setError(err.response?.data?.detail || "Ошибка загрузки"))
            .finally(() => setIsLoading(false));
    }, [id, page, perPage, debouncedSearch]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const handlePerPageChange = (newPerPage: number) => {
        setPerPage(newPerPage);
        setPage(1);
    };

    const getTextColor = (res: any) => {
        if (res.verdict === 'OK') return 'text-green-500';
        if (res.verdict === 'PARTIAL') return 'text-yellow-500';
        if (res.verdict === 'WA' || (res.tries > 0 && res.score === 0)) return 'text-red-500';
        return 'text-slate-300 dark:text-slate-700';
    };

    const formatSubmissionTime = (timeStr: string | null) => {
        if (!timeStr) return null;
        const date = new Date(timeStr);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    const renderCellContent = (res: any, contestType: string) => {
        if (res.tries === 0 && res.score === 0 && res.verdict === 'NULL') return '';

        if (contestType === 'ICPC') {
            if (res.verdict === 'OK') {
                return res.tries === 0 ? '+' : `+${res.tries}`;
            }
            return res.tries > 0 ? `-${res.tries}` : '';
        }

        return res.score;
    };

    if (error) return <div className="p-8 text-center text-red-500">{error}</div>;
    if (!data && isLoading) return (
        <div className="flex justify-center py-20">
            <RefreshCw className="animate-spin text-blue-600" size={32} />
        </div>
    );
    if (!data) return null;

    return (
        <div className="space-y-6 animate-in fade-in duration-500 h-full flex flex-col">
            <div className="flex items-center gap-4">
                <button onClick={() => navigate('/contests')}
                        className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors">
                    <ArrowLeft size={24} className="text-slate-500" />
                </button>
                <div className="flex-1">
                    <h1 className="text-2xl font-bold dark:text-white">{data.contest_name}</h1>
                    <span className="text-[10px] px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded font-bold uppercase">
                        {data.contest_type}
                    </span>
                </div>
            </div>

            {/* Поиск по участникам */}
            <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                <input
                    type="text"
                    placeholder="Поиск по имени или логину участника..."
                    className="w-full bg-white dark:bg-slate-900 dark:text-white rounded-2xl py-3 pl-12 pr-4 outline-none border border-slate-100 dark:border-slate-800 focus:ring-2 focus:ring-blue-500 text-sm"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                />
                {isLoading && (
                    <RefreshCw className="absolute right-4 top-1/2 -translate-y-1/2 animate-spin text-blue-500" size={16} />
                )}
            </div>

            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm overflow-hidden flex-1">
                <div className="overflow-x-auto w-full custom-scrollbar">
                    <table className={`w-full text-left border-collapse min-w-max transition-opacity ${isLoading ? 'opacity-50' : ''}`}>
                        <thead>
                        <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-800">
                            <th className="px-6 py-4 font-bold dark:text-white w-16 text-center">#</th>
                            <th className="px-6 py-4 font-bold dark:text-white min-w-50">Участник</th>
                            <th className="px-6 py-4 font-bold dark:text-white text-center w-20 border-l border-slate-100 dark:border-slate-800">Σ</th>
                            {data.tasks.map((task: any, i: number) => (
                                <th key={i} title={task.full_name}
                                    className="px-2 py-4 font-bold text-center dark:text-white border-l border-slate-100 dark:border-slate-800 min-w-20">
                                    {task.short_name}
                                </th>
                            ))}
                        </tr>
                        </thead>
                        <tbody>
                        {data.rows.map((row: any) => (
                            <tr key={row.id}
                                className="border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                                <td className="px-6 py-4 text-center font-bold text-slate-400 text-xs">{row.rank}</td>
                                <td className="px-6 py-4">
                                    <div className="font-bold dark:text-white text-sm">{row.name}</div>
                                    <div className="text-[10px] text-slate-400 font-mono">@{row.login}</div>
                                </td>
                                <td className="px-4 py-4 text-center font-black text-slate-700 dark:text-slate-300 border-l border-slate-100 dark:border-slate-800">
                                    {row.total_score}
                                </td>
                                {row.results.map((res: any, idx: number) => {
                                    const cellText = renderCellContent(res, data.contest_type);
                                    return (
                                        <td key={idx}
                                            className="px-1 py-2 border-l border-slate-50 dark:border-slate-800/20">
                                            <div className="flex flex-col items-center justify-center min-h-11">
                                                <span className={`font-black text-base leading-tight ${getTextColor(res)}`}>
                                                    {cellText}
                                                </span>
                                                {data.contest_type !== 'ICPC' && res.tries > 0 && (
                                                    <span className="text-[8px] text-slate-400 uppercase font-bold">
                                                        {res.tries} {res.tries === 1 ? 'try' : 'tries'}
                                                    </span>
                                                )}
                                                {res.time && (
                                                    <div className="flex items-center gap-0.5 text-[9px] text-slate-400 opacity-60 mt-0.5 font-mono">
                                                        <Clock size={8} />
                                                        {formatSubmissionTime(res.time)}
                                                    </div>
                                                )}
                                            </div>
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                        </tbody>
                    </table>
                </div>
                {!isLoading && data.rows.length === 0 && (
                    <div className="p-12 text-center text-slate-500">Участников не найдено</div>
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