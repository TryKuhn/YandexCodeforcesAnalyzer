import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Loader2,
    AlertTriangle,
    User,
    ChevronRight,
    CheckCircle2
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
    const [perPage, setPerPage] = useState(20);
    const [pagination, setPagination] = useState<PaginationData>({
        page: 1,
        per_page: 20,
        total: 0,
        total_pages: 1,
    });

    const [availableTasks, setAvailableTasks] = useState<string[]>([]);
    const [selectedTask, setSelectedTask] = useState<string | null>(null);

    const fetchReport = useCallback(async (silent = false) => {
        if (!reportId) return;
        if (!silent) setIsLoading(true);

        try {
            const res = await api.get(`/analytics/reports/${reportId}`, {
                params: {
                    page,
                    per_page: perPage,
                    task_name: selectedTask,
                },
            });

            setStatus(res.data.status);
            setPairs(res.data.pairs || []);
            setAvailableTasks(res.data.tasks || []);
            setPagination(res.data.pagination || {
                page: 1,
                per_page: 20,
                total: 0,
                total_pages: 1,
            });
        } catch {
            setStatus('failed');
        } finally {
            // Always clear loading — including silent calls that transition from
            // 'processing' to 'completed', so the spinner doesn't stay forever.
            setIsLoading(false);
        }
    }, [reportId, page, perPage, selectedTask]);

    // Initial load + re-fetch when page / perPage / selectedTask changes
    useEffect(() => {
        fetchReport();
    }, [fetchReport]);

    useEffect(() => {
        setPage(1);
    }, [selectedTask]);

    // Polling while the report is still being processed
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
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold dark:text-white flex items-center gap-3">
                    <AlertTriangle className="text-amber-500" />
                    Подозрительные пары
                    {isLoading && <Loader2 size={18} className="animate-spin text-blue-500" />}
                </h1>

                <div className="flex items-center gap-2 text-xs font-bold text-slate-400 bg-slate-100 dark:bg-slate-800 px-3 py-1.5 rounded-full">
                    <CheckCircle2 size={14} className="text-green-500" />
                    АНАЛИЗ ЗАВЕРШЕН
                </div>
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


            <div className={`grid grid-cols-1 gap-3 transition-opacity ${isLoading ? 'opacity-50' : ''}`}>
                {pairs.map((pair) => (
                    <button
                        key={pair.id}
                        onClick={() => navigate(`/contests/${id}/analytics/compare/${pair.id}`)}
                        className="w-full bg-white dark:bg-slate-900 p-5 rounded-3xl border border-slate-100 dark:border-slate-800 flex items-center justify-between hover:border-blue-500/50 hover:shadow-lg transition-all group"
                    >
                        <div className="flex items-center gap-8">
                            <div className="text-center w-16">
                                <div className={`text-2xl font-black ${pair.percent > 90 ? 'text-red-600' : 'text-orange-500'}`}>
                                    {pair.percent}%
                                </div>
                                <div className="text-[10px] font-bold text-slate-400 uppercase">Match</div>
                            </div>

                            <div className="flex items-center gap-6">
                                <div className="text-left">
                                    <p className="text-xs text-slate-400 font-bold mb-1">УЧАСТНИК 1</p>
                                    <ParticipantLabel login={pair.user1} name={pair.user1_name} />
                                </div>

                                <div className="h-10 w-px bg-slate-100 dark:bg-slate-800"></div>

                                <div className="text-left">
                                    <p className="text-xs text-slate-400 font-bold mb-1">УЧАСТНИК 2</p>
                                    <ParticipantLabel login={pair.user2} name={pair.user2_name} />
                                </div>
                            </div>

                            <div className="hidden lg:block px-4 py-2 bg-slate-50 dark:bg-slate-800 rounded-2xl">
                                <p className="text-[10px] text-slate-400 font-bold mb-1 uppercase text-left">
                                    Задача
                                </p>
                                <p className="text-xs font-bold dark:text-slate-200">
                                    {pair.task_name}
                                </p>
                            </div>
                        </div>

                        <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded-full text-slate-300 group-hover:text-blue-600 transition-colors">
                            <ChevronRight size={20} />
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
