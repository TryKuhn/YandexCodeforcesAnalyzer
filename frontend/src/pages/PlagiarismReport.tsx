import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Loader2,
    AlertTriangle,
    User,
    ChevronRight,
    CheckCircle2,
    Search,
    ShieldCheck,
    ShieldBan,
} from 'lucide-react';
import { api } from '../api/instance';
import { Pagination } from '../components/Pagination';

type ReportStatus = 'processing' | 'completed' | 'failed';

interface Pair {
    id: number;
    sub1: string;
    sub2: string;
    user1: string;
    user1_name?: string | null;
    user2: string;
    user2_name?: string | null;
    task_name: string;
    percent: number;
}

interface PaginationData {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
}

const ParticipantLabel = ({ login, name }: { login: string; name?: string | null }) => (
    <div className="flex items-center gap-2 text-sm font-bold dark:text-white">
        <User size={14} className="text-blue-500 shrink-0" />
        <div>
            <div>{name || login}</div>
            {name && <div className="text-xs font-normal text-slate-400">{login}</div>}
        </div>
    </div>
);

export const PlagiarismReport = () => {
    const { id, reportId } = useParams();
    const navigate = useNavigate();

    const [status, setStatus] = useState<ReportStatus>('processing');
    const [pairs, setPairs] = useState<Pair[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const [page, setPage] = useState(1);
    const [perPage, setPerPage] = useState(10);
    const [pagination, setPagination] = useState<PaginationData>({
        page: 1,
        per_page: 10,
        total: 0,
        total_pages: 1,
    });

    const [availableTasks, setAvailableTasks] = useState<string[]>([]);
    const [bannedTasks, setBannedTasks] = useState<Set<string>>(new Set());
    const [selectedTask, setSelectedTask] = useState<string | null>(null);
    const [search, setSearch] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [isBanToggling, setIsBanToggling] = useState(false);

    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(search);
            setPage(1);
        }, 400);
        return () => clearTimeout(timer);
    }, [search]);

    const fetchReport = useCallback(async (silent = false) => {
        if (!reportId) return;
        if (!silent) setIsLoading(true);

        try {
            const res = await api.get(`/analytics/reports/${reportId}`, {
                params: {
                    page,
                    per_page: perPage,
                    ...(selectedTask ? { task_name: selectedTask } : {}),
                    ...(debouncedSearch.trim() ? { search: debouncedSearch.trim() } : {}),
                },
            });

            setStatus(res.data.status);
            setPairs(res.data.pairs || []);
            setAvailableTasks(res.data.tasks || []);
            setBannedTasks(new Set(res.data.banned_tasks || []));
            setPagination(res.data.pagination || {
                page: 1,
                per_page: 10,
                total: 0,
                total_pages: 1,
            });
        } catch {
            setStatus('failed');
        } finally {
            setIsLoading(false);
        }
    }, [reportId, page, perPage, selectedTask, debouncedSearch]);

    useEffect(() => {
        fetchReport();
    }, [fetchReport]);

    useEffect(() => {
        setPage(1);
    }, [selectedTask, debouncedSearch]);

    useEffect(() => {
        if (status !== 'processing') return;

        const interval = setInterval(() => {
            fetchReport(true);
        }, 2000);

        return () => clearInterval(interval);
    }, [status, fetchReport]);

    const handlePerPageChange = (newPerPage: number) => {
        setPerPage(newPerPage);
        setPage(1);
    };

    const isCurrentTaskBanned = selectedTask
        ? bannedTasks.has(selectedTask)
        : availableTasks.length > 0 && availableTasks.every(t => bannedTasks.has(t));

    const handleBanToggle = async () => {
        const banning = !isCurrentTaskBanned;
        const verb = banning ? 'Забанить' : 'Разбанить';
        const label = selectedTask ? `задачу «${selectedTask}»` : 'всё';
        const hint = banning ? 'Это обнулит очки участников.' : 'Это вернёт очки участникам.';
        if (!confirm(`${verb} ${label}? ${hint}`)) return;

        setIsBanToggling(true);
        try {
            const endpoint = banning ? 'ban-task' : 'unban-task';
            await api.post(`/analytics/reports/${reportId}/${endpoint}`, null, {
                params: selectedTask ? { task_name: selectedTask } : {},
            });
            fetchReport();
        } catch {
            alert('Ошибка при изменении статуса бана');
        } finally {
            setIsBanToggling(false);
        }
    };

    if (status === 'processing') {
        return (
            <div className="h-100 flex flex-col items-center justify-center space-y-4 bg-white dark:bg-slate-900 rounded-3xl border border-dashed border-slate-200 dark:border-slate-800">
                <Loader2 size={48} className="animate-spin text-blue-600" />
                <div className="text-center">
                    <h2 className="text-xl font-bold dark:text-white">Анализ в процессе...</h2>
                    <p className="text-slate-500 text-sm mt-1">
                        Сравниваем AST-деревья и токены решений
                    </p>
                </div>
            </div>
        );
    }

    if (status === 'failed') {
        return (
            <div className="h-100 flex flex-col items-center justify-center space-y-4 bg-white dark:bg-slate-900 rounded-3xl border border-dashed border-red-200 dark:border-red-900/30">
                <AlertTriangle size={48} className="text-red-500" />
                <div className="text-center">
                    <h2 className="text-xl font-bold dark:text-white">Не удалось загрузить отчёт</h2>
                    <p className="text-slate-500 text-sm mt-1">
                        Попробуй обновить страницу позже
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="flex flex-wrap justify-between items-center gap-3">
                <h1 className="text-xl sm:text-2xl font-bold dark:text-white flex items-center gap-2 sm:gap-3">
                    <AlertTriangle className="text-amber-500 shrink-0" />
                    Подозрительные пары
                    {isLoading && <Loader2 size={18} className="animate-spin text-blue-500" />}
                </h1>

                <div className="flex items-center gap-2">
                    {availableTasks.length > 0 && (
                        <button
                            onClick={handleBanToggle}
                            disabled={isBanToggling}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all disabled:opacity-50 ${
                                isCurrentTaskBanned
                                    ? 'bg-white dark:bg-slate-900 text-green-600 dark:text-green-400 border border-green-200 dark:border-green-800 hover:bg-green-50 dark:hover:bg-green-900/20'
                                    : 'bg-white dark:bg-slate-900 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800 hover:bg-red-50 dark:hover:bg-red-900/20'
                            }`}
                        >
                            {isBanToggling
                                ? <Loader2 size={13} className="animate-spin" />
                                : isCurrentTaskBanned
                                    ? <ShieldCheck size={13} />
                                    : <ShieldBan size={13} />
                            }
                            {isCurrentTaskBanned
                                ? (selectedTask ? `Разбанить «${selectedTask}»` : 'Разбанить всё')
                                : (selectedTask ? `Забанить «${selectedTask}»` : 'Забанить всё')
                            }
                        </button>
                    )}
                    <div className="flex items-center gap-2 text-xs font-bold text-slate-400 bg-slate-100 dark:bg-slate-800 px-3 py-1.5 rounded-full">
                        <CheckCircle2 size={14} className="text-green-500" />
                        АНАЛИЗ ЗАВЕРШЕН
                    </div>
                </div>
            </div>

            <div className="flex flex-col gap-3">
                <div className="relative">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                    <input
                        type="text"
                        placeholder="Поиск по логину участника..."
                        className="w-full bg-white dark:bg-slate-900 dark:text-white rounded-2xl py-2.5 pl-10 pr-4 outline-none border border-slate-100 dark:border-slate-800 focus:ring-2 focus:ring-blue-500 text-sm"
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                </div>

                {availableTasks.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                        <button
                            onClick={() => setSelectedTask(null)}
                            className={`px-4 py-2 rounded-2xl text-xs font-bold transition-all ${
                                selectedTask === null
                                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/30'
                                    : 'bg-white dark:bg-slate-900 text-slate-500 border border-slate-100 dark:border-slate-800 hover:border-blue-500/50'
                            }`}
                        >
                            Все задачи
                        </button>
                        {availableTasks.map(task => (
                            <button
                                key={task}
                                onClick={() => setSelectedTask(task)}
                                className={`px-4 py-2 rounded-2xl text-xs font-bold transition-all ${
                                    selectedTask === task
                                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/30'
                                        : 'bg-white dark:bg-slate-900 text-slate-500 border border-slate-100 dark:border-slate-800 hover:border-blue-500/50'
                                }`}
                            >
                                {task}
                            </button>
                        ))}
                    </div>
                )}
            </div>


            <div className={`grid grid-cols-1 gap-3 transition-opacity ${isLoading ? 'opacity-50' : ''}`}>
                {pairs.map((pair) => (
                    <button
                        key={pair.id}
                        onClick={() => navigate(`/contests/${id}/analytics/compare/${pair.id}`)}
                        className="w-full bg-white dark:bg-slate-900 p-4 sm:p-5 rounded-3xl border border-slate-100 dark:border-slate-800 flex items-center justify-between gap-3 hover:border-blue-500/50 hover:shadow-lg transition-all group"
                    >
                        <div className="flex items-center gap-3 sm:gap-6 flex-1 min-w-0">
                            <div className="text-center shrink-0">
                                <div className={`text-xl sm:text-2xl font-black ${pair.percent > 90 ? 'text-red-600' : 'text-orange-500'}`}>
                                    {pair.percent}%
                                </div>
                                <div className="text-[9px] font-bold text-slate-400 uppercase">Match</div>
                            </div>

                            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-6 min-w-0 flex-1">
                                <div className="text-left min-w-0">
                                    <p className="text-[10px] text-slate-400 font-bold mb-0.5">УЧАСТНИК 1</p>
                                    <ParticipantLabel login={pair.user1} name={pair.user1_name} />
                                </div>

                                <div className="hidden sm:block h-10 w-px bg-slate-100 dark:bg-slate-800 shrink-0"></div>

                                <div className="text-left min-w-0">
                                    <p className="text-[10px] text-slate-400 font-bold mb-0.5">УЧАСТНИК 2</p>
                                    <ParticipantLabel login={pair.user2} name={pair.user2_name} />
                                </div>
                            </div>

                            <div className="hidden lg:block px-3 py-2 bg-slate-50 dark:bg-slate-800 rounded-2xl shrink-0">
                                <p className="text-[10px] text-slate-400 font-bold mb-1 uppercase">Задача</p>
                                <p className="text-xs font-bold dark:text-slate-200">{pair.task_name}</p>
                            </div>
                        </div>

                        <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded-full text-slate-300 group-hover:text-blue-600 transition-colors shrink-0">
                            <ChevronRight size={18} />
                        </div>
                    </button>
                ))}
            </div>

            {!isLoading && pairs.length === 0 && (
                <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-100 dark:border-slate-800 p-12 text-center text-slate-500">
                    Подозрительных пар не найдено
                </div>
            )}

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
