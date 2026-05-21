import { Outlet, Link, useParams, useLocation } from 'react-router-dom';
import {Table, FileCode, BarChart3, Info, ChevronLeft, Download} from 'lucide-react';

export const ContestLayout = () => {
    const { id } = useParams();
    const location = useLocation();

    const tabs = [
        { icon: Info,     label: 'Обзор',     path: `/contests/${id}` },
        { icon: Table,    label: 'Таблица',   path: `/contests/${id}/table` },
        { icon: Download, label: 'Импорт',    path: `/contests/${id}/import-submissions` },
        { icon: FileCode, label: 'Посылки',   path: `/contests/${id}/submissions` },
        { icon: BarChart3,label: 'Аналитика', path: `/contests/${id}/analytics` },
    ];

    return (
        <div className="flex flex-col space-y-4 lg:space-y-6">
            <div className="flex items-center gap-3">
                <Link
                    to="/contests"
                    className="p-2 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-full transition-colors shrink-0"
                >
                    <ChevronLeft size={20} className="text-slate-500" />
                </Link>
                <h2 className="text-base lg:text-xl font-bold dark:text-white truncate">
                    Соревнование #{id}
                </h2>
            </div>

            <div className="flex flex-col lg:flex-row gap-4 lg:gap-6">
                <nav className="
                    flex lg:flex-col gap-1
                    lg:w-56 lg:shrink-0
                    overflow-x-auto lg:overflow-visible
                    -mx-4 px-4 lg:mx-0 lg:px-0
                    pb-1 lg:pb-0
                ">
                    {tabs.map((tab) => {
                        const isActive = location.pathname === tab.path;
                        return (
                            <Link
                                key={tab.path}
                                to={tab.path}
                                className={`
                                    flex items-center gap-2 px-3 lg:px-4 py-2 lg:py-3
                                    rounded-xl transition-all font-medium
                                    whitespace-nowrap shrink-0
                                    text-xs lg:text-sm
                                    ${isActive
                                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                                        : 'text-slate-500 hover:bg-white dark:hover:bg-slate-800 bg-white/50 dark:bg-slate-800/50'}
                                `}
                            >
                                <tab.icon size={15} />
                                {tab.label}
                            </Link>
                        );
                    })}
                </nav>

                <main className="flex-1 min-w-0">
                    <Outlet />
                </main>
            </div>
        </div>
    );
};
