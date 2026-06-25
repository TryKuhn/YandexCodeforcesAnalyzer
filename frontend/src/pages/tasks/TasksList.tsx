// pages/tasks/TasksList.tsx

import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
    LayoutList, Plus, Loader2, Puzzle, ChevronRight,
    Clock, X, AlertCircle, Search,
} from 'lucide-react';
import { api } from '../../api/instance';
import { Pagination } from '../../components/Pagination';

interface PolygonProblem {
    polygon_id: number;
    name: string;
    statement_name: string | null;
    owner: string;
    access_type: string | null;
    revision: number | null;
    modified: boolean;
    deleted: boolean;
    list_fetched_at: string | null;
}

interface PaginatedResponse {
    items: PolygonProblem[];
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
}

const PER_PAGE_KEY = 'tasks_per_page';

const ACCESS_BADGE: Record<string, { label: string; color: string; bg: string }> = {
    OWNER: {
        label: 'OWNER',
        color: 'text-violet-600 dark:text-violet-400',
        bg: 'bg-violet-50 dark:bg-violet-900/20',
    },
    WRITE: {
        label: 'WRITE',
        color: 'text-blue-600 dark:text-blue-400',
        bg: 'bg-blue-50 dark:bg-blue-900/20',
    },
    READ: {
        label: 'READ',
        color: 'text-slate-600 dark:text-slate-400',
        bg: 'bg-slate-100 dark:bg-slate-800',
    },
};

const formatRelative = (dateStr: string | null): string => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const diff = Date.now() - date.getTime();
    if (diff < 60_000) return 'только что';
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} мин назад`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} ч назад`;
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
};

function readPerPage(): number {
    try {
        const v = localStorage.getItem(PER_PAGE_KEY);
        const n = v ? parseInt(v, 10) : NaN;
        return Number.isFinite(n) && n > 0 ? n : 10;
    } catch {
        return 10;
    }
}

export const TasksList = () => {
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const initialPage = Math.max(1, Number(searchParams.get('page')) || 1);

    const [problems, setProblems] = useState<PolygonProblem[]>([]);
    const [total, setTotal] = useState(0);
    const [totalPages, setTotalPages] = useState(1);
    const [page, setPage] = useState(initialPage);
    const [perPage, setPerPage] = useState<number>(readPerPage);

    const syncPageToUrl = (p: number) => {
        setSearchParams(prev => {
            const next = new URLSearchParams(prev);
            if (p <= 1) next.delete('page'); else next.set('page', String(p));
            return next;
        }, { replace: true });
    };

    const [search, setSearch] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [polygonNotConfigured, setPolygonNotConfigured] = useState(false);

    const [showCreate, setShowCreate] = useState(false);
    const [newName, setNewName] = useState('');
    const [creating, setCreating] = useState(false);
    const [createError, setCreateError] = useState<string | null>(null);

    const fetchProblems = async (
        p = page,
        pp = perPage,
        q = debouncedSearch,
        doRefresh = false,
    ) => {
        setLoading(true);
        setError(null);
        setPolygonNotConfigured(false);
        try {
            const res = await api.get<PaginatedResponse>('/polygon/problems/', {
                params: { page: p, per_page: pp, search: q, refresh: doRefresh },
            });
            const data = res.data;
            setProblems(data.items);
            setTotal(data.total);
            setTotalPages(data.total_pages);
            setPage(data.page);
        } catch (e: any) {
            if (e?.response?.status === 401 || e?.response?.status === 403) {
                setPolygonNotConfigured(true);
            } else {
                setError(e?.response?.data?.detail || 'Не удалось загрузить задачи');
            }
        } finally {
            setLoading(false);
        }
    };

    // Initial load with Polygon refresh, honouring the page from the URL
    useEffect(() => {
        fetchProblems(initialPage, perPage, '', true);
    }, []);

    // Re-fetch when debounced search changes (after initial mount)
    const isFirstRender = useRef(true);
    useEffect(() => {
        if (isFirstRender.current) { isFirstRender.current = false; return; }
        setPage(1);
        syncPageToUrl(1);
        fetchProblems(1, perPage, debouncedSearch, false);
    }, [debouncedSearch]);

    const handleSearchChange = (value: string) => {
        setSearch(value);
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => setDebouncedSearch(value), 300);
    };

    const clearSearch = () => {
        setSearch('');
        setDebouncedSearch('');
        if (debounceRef.current) clearTimeout(debounceRef.current);
    };

    const handlePageChange = (newPage: number) => {
        setPage(newPage);
        syncPageToUrl(newPage);
        fetchProblems(newPage, perPage, debouncedSearch, false);
    };

    const handlePerPageChange = (newPerPage: number) => {
        setPerPage(newPerPage);
        try { localStorage.setItem(PER_PAGE_KEY, String(newPerPage)); } catch { /* ignore */ }
        setPage(1);
        syncPageToUrl(1);
        fetchProblems(1, newPerPage, debouncedSearch, false);
    };

    const handleCreate = async () => {
        if (!newName.trim() || creating) return;
        setCreating(true);
        setCreateError(null);
        try {
            const res = await api.post('/polygon/problems/', { name: newName.trim() });
            navigate(`/tasks/${res.data.polygon_id}`);
        } catch (e: any) {
            setCreateError(e?.response?.data?.detail || 'Ошибка создания задачи');
        } finally {
            setCreating(false);
        }
    };

    return (
        <>
            <div className="max-w-4xl mx-auto py-4 sm:py-6">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 sm:mb-8">
                    <div>
                        <h1 className="text-2xl sm:text-3xl font-black text-slate-800 dark:text-white flex items-center gap-3">
                            <LayoutList className="text-blue-500" size={28} />
                            Задачи
                        </h1>
                        <p className="text-slate-500 mt-1 text-sm">
                            Управление задачами в Polygon
                        </p>
                    </div>
                    <button
                        onClick={() => { setShowCreate(true); setNewName(''); setCreateError(null); }}
                        className="flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-blue-700
                                   hover:from-blue-700 hover:to-blue-800 text-white
                                   w-full sm:w-auto px-5 py-3 rounded-2xl font-bold text-sm
                                   transition-all shadow-lg shadow-blue-500/20
                                   hover:shadow-xl active:scale-95 shrink-0"
                    >
                        <Plus size={18} />
                        Задача
                    </button>
                </div>

                {/* Search */}
                <div className="relative mb-4">
                    <Search
                        size={15}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
                    />
                    <input
                        type="text"
                        value={search}
                        onChange={e => handleSearchChange(e.target.value)}
                        placeholder="Поиск по названию задачи..."
                        className="w-full pl-9 pr-9 py-2.5 text-sm bg-white dark:bg-slate-900
                                   border border-slate-200 dark:border-slate-700 rounded-2xl outline-none
                                   dark:text-white placeholder:text-slate-400
                                   focus:border-blue-400 dark:focus:border-blue-600 transition-all"
                    />
                    {search && (
                        <button
                            onClick={clearSearch}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400
                                       hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                        >
                            <X size={14} />
                        </button>
                    )}
                </div>

                {/* Body */}
                {loading ? (
                    <div className="flex flex-col items-center justify-center py-20">
                        <Loader2 size={32} className="animate-spin text-blue-500 mb-4" />
                        <p className="text-slate-400 text-sm">Загрузка задач из Polygon...</p>
                    </div>
                ) : polygonNotConfigured ? (
                    <div className="flex flex-col items-center justify-center py-20 text-center">
                        <AlertCircle size={48} className="mb-4 text-amber-400" />
                        <p className="font-bold text-lg text-slate-700 dark:text-slate-200 mb-2">
                            Polygon API не настроен
                        </p>
                        <p className="text-slate-500 text-sm mb-4">
                            Для работы с задачами необходимо указать ключи Polygon API.
                        </p>
                        <button
                            onClick={() => navigate('/profile')}
                            className="text-blue-500 hover:text-blue-700 font-bold text-sm underline underline-offset-2"
                        >
                            Настройте Polygon API в профиле
                        </button>
                    </div>
                ) : error ? (
                    <div className="flex flex-col items-center justify-center py-20 text-center">
                        <AlertCircle size={48} className="mb-4 text-red-400" />
                        <p className="font-bold text-slate-700 dark:text-slate-200 mb-2">{error}</p>
                        <button
                            onClick={() => fetchProblems(page, perPage, debouncedSearch, true)}
                            className="text-blue-500 hover:text-blue-700 font-bold text-sm"
                        >
                            Попробовать снова
                        </button>
                    </div>
                ) : problems.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20 text-slate-400">
                        <Puzzle size={64} className="mb-4 opacity-10" />
                        {debouncedSearch ? (
                            <>
                                <p className="font-bold text-lg">Ничего не найдено</p>
                                <p className="text-sm mt-2">
                                    По запросу <span className="font-mono">«{debouncedSearch}»</span> задач не найдено
                                </p>
                                <button
                                    onClick={clearSearch}
                                    className="mt-3 text-blue-500 hover:text-blue-700 font-bold text-sm"
                                >
                                    Сбросить поиск
                                </button>
                            </>
                        ) : (
                            <>
                                <p className="font-bold text-lg">Нет задач</p>
                                <p className="text-sm mt-2">Нажмите «+ Задача», чтобы создать первую</p>
                            </>
                        )}
                    </div>
                ) : (
                    <>
                        {debouncedSearch && (
                            <p className="text-xs text-slate-400 mb-3">
                                Найдено: {total} {total === 1 ? 'задача' : total < 5 ? 'задачи' : 'задач'}
                                {' '}по запросу «{debouncedSearch}»
                            </p>
                        )}

                        <div className="space-y-2 mb-6">
                            {problems.map(problem => {
                                const badge = ACCESS_BADGE[problem.access_type || ''] || ACCESS_BADGE.READ;
                                const displayName = problem.statement_name || problem.name;

                                return (
                                    <div
                                        key={problem.polygon_id}
                                        onClick={() => navigate(`/tasks/${problem.polygon_id}`)}
                                        className="group bg-white dark:bg-slate-900 rounded-2xl
                                                   border border-slate-200 dark:border-slate-800
                                                   cursor-pointer transition-all
                                                   hover:border-blue-300 dark:hover:border-blue-700
                                                   hover:shadow-lg hover:shadow-blue-500/5
                                                   active:scale-[0.99] p-4 sm:p-5"
                                    >
                                        <div className="flex items-center justify-between gap-4">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-baseline gap-2 min-w-0">
                                                    <h3 className="font-bold text-base truncate transition-colors text-slate-800 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400">
                                                        {displayName}
                                                    </h3>
                                                    {problem.statement_name && (
                                                        <span className="text-[11px] text-slate-400 font-mono truncate shrink-0 hidden sm:block">
                                                            {problem.name}
                                                        </span>
                                                    )}
                                                </div>

                                                <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                                                    <span className="text-[11px] text-slate-400 font-mono">
                                                        #{problem.polygon_id}
                                                    </span>

                                                    {problem.access_type && (
                                                        <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${badge.color} ${badge.bg}`}>
                                                            {badge.label}
                                                        </span>
                                                    )}

                                                    {problem.revision !== null && (
                                                        <span className="text-[11px] text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">
                                                            rev.&nbsp;{problem.revision}
                                                        </span>
                                                    )}

                                                    {problem.modified && (
                                                        <span className="text-[11px] font-bold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 px-2 py-0.5 rounded-full">
                                                            изменено
                                                        </span>
                                                    )}

                                                    {problem.list_fetched_at && (
                                                        <span className="flex items-center gap-1 text-[11px] text-slate-400">
                                                            <Clock size={10} />
                                                            {formatRelative(problem.list_fetched_at)}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>

                                            <ChevronRight
                                                size={20}
                                                className="text-slate-300 dark:text-slate-700 group-hover:text-blue-500 transition-colors shrink-0"
                                            />
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Pagination */}
                        {(totalPages > 1 || problems.length > 0) && (
                            <div className="mt-4 py-4 border-t border-slate-200 dark:border-slate-800">
                                <Pagination
                                    page={page}
                                    totalPages={totalPages}
                                    total={total}
                                    perPage={perPage}
                                    onPageChange={handlePageChange}
                                    onPerPageChange={handlePerPageChange}
                                />
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* Create dialog */}
            {showCreate && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 sm:p-8 w-full max-w-md shadow-2xl">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-black dark:text-white flex items-center gap-2">
                                <Plus size={20} className="text-blue-500" />
                                Новая задача
                            </h2>
                            <button
                                onClick={() => setShowCreate(false)}
                                className="p-2 text-slate-400 hover:text-slate-700 dark:hover:text-white rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
                            >
                                <X size={18} />
                            </button>
                        </div>
                        <p className="text-sm text-slate-500 mb-4">
                            Введите системное имя задачи (на латинице). Задача будет создана в вашем аккаунте Polygon.
                        </p>
                        <input
                            type="text"
                            value={newName}
                            onChange={e => setNewName(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') handleCreate(); }}
                            placeholder="my-problem-name"
                            className="w-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800
                                       rounded-2xl px-4 py-3 text-sm dark:text-white outline-none
                                       focus:border-blue-500 transition-all mb-3"
                            autoFocus
                        />
                        {createError && (
                            <p className="text-sm text-red-500 mb-3">{createError}</p>
                        )}
                        <button
                            onClick={handleCreate}
                            disabled={creating || !newName.trim()}
                            className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-2xl font-bold
                                       flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                        >
                            {creating ? <Loader2 size={18} className="animate-spin" /> : <Plus size={18} />}
                            Создать
                        </button>
                    </div>
                </div>
            )}
        </>
    );
};
