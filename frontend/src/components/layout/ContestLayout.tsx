import { Outlet, Link, useParams, useLocation } from 'react-router-dom';
import {Table, FileCode, BarChart3, Info, ChevronLeft, Download} from 'lucide-react';

export const ContestLayout = () => {
    const { id } = useParams();
    const location = useLocation();

    const tabs = [
        { icon: Info, label: 'Обзор', path: `/contests/${id}` },
        { icon: Table, label: 'Таблица результатов', path: `/contests/${id}/table` },
        { icon: Download, label: 'Импорт посылок', path: `/contests/${id}/import-submissions` },
        { icon: FileCode, label: 'Посылки участников', path: `/contests/${id}/submissions` },
        { icon: BarChart3, label: 'Аналитика и Плагиат', path: `/contests/${id}/analytics` },
    ];

    return (
        <div className="flex flex-col h-full space-y-6">
            <div className="flex items-center gap-4">
                <Link to="/contests" className="p-2 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-full transition-colors">
                    <ChevronLeft size={20} className="text-slate-500" />
                </Link>
                <h2 className="text-xl font-bold dark:text-white">Управление соревнованием #{id}</h2>
            </div>

            <div className="flex gap-6 h-full">
                <aside className="w-64 space-y-2 flex-shrink-0">
                    {tabs.map((tab) => {
                        const isActive = location.pathname === tab.path;
                        return (
                            <Link
                                key={tab.path}
                                to={tab.path}
                                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium ${
                                    isActive
                                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                                        : 'text-slate-500 hover:bg-white dark:hover:bg-slate-800 bg-transparent'
                                }`}
                            >
                                <tab.icon size={18} />
                                <span className="text-sm">{tab.label}</span>
                            </Link>
                        );
                    })}
                </aside>

                <main className="flex-1 min-w-0">
                    <Outlet />
                </main>
            </div>
        </div>
    );
};
