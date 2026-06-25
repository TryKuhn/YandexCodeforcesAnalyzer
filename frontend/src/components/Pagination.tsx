import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

interface PaginationProps {
    page: number;
    totalPages: number;
    total: number;
    perPage: number;
    onPageChange: (page: number) => void;
    onPerPageChange: (perPage: number) => void;
}

export const Pagination = ({ page, totalPages, total, perPage, onPageChange, onPerPageChange }: PaginationProps) => {
    const getPageNumbers = () => {
        const pages: (number | string)[] = [];
        const delta = 2;

        if (totalPages <= 7) {
            for (let i = 1; i <= totalPages; i++) pages.push(i);
            return pages;
        }

        pages.push(1);
        if (page - delta > 2) pages.push('...');

        for (let i = Math.max(2, page - delta); i <= Math.min(totalPages - 1, page + delta); i++) {
            pages.push(i);
        }

        if (page + delta < totalPages - 1) pages.push('...');
        if (totalPages > 1) pages.push(totalPages);

        return pages;
    };

    const from = (page - 1) * perPage + 1;
    const to = Math.min(page * perPage, total);

    return (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 px-2">
            {/* Информация и выбор размера страницы */}
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm text-slate-500">
                <span>
                    Показано <span className="font-bold text-slate-700 dark:text-slate-300">{from}–{to}</span> из{' '}
                    <span className="font-bold text-slate-700 dark:text-slate-300">{total}</span>
                </span>
                <select
                    value={perPage}
                    onChange={(e) => onPerPageChange(Number(e.target.value))}
                    className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:text-white cursor-pointer"
                >
                    {[10, 25, 50, 100].map(n => (
                        <option key={n} value={n}>{n} / стр.</option>
                    ))}
                </select>
            </div>

            {/* Кнопки навигации */}
            <div className="flex flex-wrap items-center justify-center gap-1">
                <button
                    onClick={() => onPageChange(1)}
                    disabled={page === 1}
                    className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                    title="Первая страница"
                >
                    <ChevronsLeft size={16} className="text-slate-500" />
                </button>
                <button
                    onClick={() => onPageChange(page - 1)}
                    disabled={page === 1}
                    className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                    title="Предыдущая"
                >
                    <ChevronLeft size={16} className="text-slate-500" />
                </button>

                {getPageNumbers().map((p, idx) =>
                    typeof p === 'string' ? (
                        <span key={`dots-${idx}`} className="px-2 text-slate-400 text-sm">…</span>
                    ) : (
                        <button
                            key={p}
                            onClick={() => onPageChange(p)}
                            className={`min-w-9 h-9 rounded-lg text-sm font-medium transition-all ${
                                p === page
                                    ? 'bg-blue-500 text-white shadow-md shadow-blue-500/25'
                                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                            }`}
                        >
                            {p}
                        </button>
                    )
                )}

                <button
                    onClick={() => onPageChange(page + 1)}
                    disabled={page === totalPages}
                    className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                    title="Следующая"
                >
                    <ChevronRight size={16} className="text-slate-500" />
                </button>
                <button
                    onClick={() => onPageChange(totalPages)}
                    disabled={page === totalPages}
                    className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                    title="Последняя страница"
                >
                    <ChevronsRight size={16} className="text-slate-500" />
                </button>
            </div>
        </div>
    );
};
