import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    ShieldAlert, Play, BarChart, AlertCircle,
    History, ChevronRight, Clock, CheckCircle2, Loader2
} from 'lucide-react';
import { api } from '../api/instance';

export const ContestAnalytics = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [reports, setReports] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // Загружаем историю отчетов при входе на страницу
    useEffect(() => {
        fetchReports();
    }, [id]);

    const fetchReports = async () => {
        try {
            // Эндпоинт для получения списка отчетов по данному контесту
            const res = await api.get(`/analytics/contests/${id}/reports`);
            setReports(res.data);
        } catch (e) {
            console.error("Ошибка при загрузке истории отчетов");
        } finally {
            setIsLoading(false);
        }
    };

    const getStatusStyle = (status: string) => {
        switch (status) {
            case 'completed': return 'text-green-500 bg-green-50 dark:bg-green-900/20';
            case 'failed': return 'text-red-500 bg-red-50 dark:bg-red-900/20';
            default: return 'text-blue-500 bg-blue-50 dark:bg-blue-900/20';
        }
    };

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            {/* Верхние карточки действий */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Карточка Антиплагиата */}
                <div className="bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm flex flex-col items-center text-center space-y-4">
                    <div className="p-4 bg-amber-100 dark:bg-amber-900/30 text-amber-600 rounded-2xl">
                        <ShieldAlert size={32} />
                    </div>
                    <div className="space-y-1">
                        <h3 className="text-xl font-bold dark:text-white">Проверка на плагиат</h3>
                        <p className="text-slate-500 text-sm">Сравнение исходных кодов с помощью C++ модуля и LSH.</p>
                    </div>
                    <button
                        onClick={() => navigate(`/contests/${id}/analytics/check`)}
                        className="w-full bg-slate-900 dark:bg-blue-600 text-white py-3.5 rounded-2xl font-bold flex justify-center items-center gap-2 hover:opacity-90 transition-all shadow-lg shadow-blue-500/10"
                    >
                        <Play size={18} />
                        <span>Настроить и запустить</span>
                    </button>
                </div>

                {/* Карточка Графиков */}
                <div className="bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm flex flex-col items-center text-center space-y-4 opacity-60">
                    <div className="p-4 bg-blue-100 dark:bg-blue-900/30 text-blue-600 rounded-2xl">
                        <BarChart size={32} />
                    </div>
                    <div className="space-y-1">
                        <h3 className="text-xl font-bold dark:text-white">Визуальная аналитика</h3>
                        <p className="text-slate-500 text-sm">Распределение баллов и статистика по задачам.</p>
                    </div>
                    <button disabled className="w-full border-2 border-slate-100 dark:border-slate-800 dark:text-white py-3 rounded-2xl font-bold cursor-not-allowed">
                        Скоро будет
                    </button>
                </div>
            </div>

            {/* Секция истории отчетов */}
            <div className="space-y-4">
                <div className="flex items-center gap-2 px-2">
                    <History size={20} className="text-slate-400" />
                    <h2 className="text-lg font-bold dark:text-white">История проверок</h2>
                </div>

                {isLoading ? (
                    <div className="py-10 flex justify-center"><Loader2 className="animate-spin text-slate-300" /></div>
                ) : reports.length > 0 ? (
                    <div className="grid grid-cols-1 gap-3">
                        {reports.map((report) => (
                            <button
                                key={report.id}
                                onClick={() => navigate(`/contests/${id}/analytics/reports/${report.id}`)}
                                className="w-full bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-100 dark:border-slate-800 flex items-center justify-between hover:border-blue-500/50 transition-all group"
                            >
                                <div className="flex items-center gap-6">
                                    <div className={`p-2.5 rounded-xl ${getStatusStyle(report.status)}`}>
                                        {report.status === 'completed' ? <CheckCircle2 size={20} /> :
                                            report.status === 'failed' ? <AlertCircle size={20} /> :
                                                <Loader2 size={20} className="animate-spin" />}
                                    </div>

                                    <div className="text-left">
                                        <p className="font-bold text-sm dark:text-white">Отчет #{report.id}</p>
                                        <div className="flex items-center gap-3 text-xs text-slate-500 mt-0.5">
                                            <span className="flex items-center gap-1"><Clock size={12}/> {new Date(report.created_at).toLocaleString()}</span>
                                            <span>•</span>
                                            <span>Порог: {Math.round(report.threshold * 100)}%</span>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-center gap-4">
                                    {report.status === 'completed' && (
                                        <span className="text-xs font-bold text-blue-600 bg-blue-50 dark:bg-blue-900/30 px-3 py-1 rounded-lg">
                                            Найдено пар: {report.pairs_count}
                                        </span>
                                    )}
                                    <ChevronRight size={20} className="text-slate-300 group-hover:text-blue-600 group-hover:translate-x-1 transition-all" />
                                </div>
                            </button>
                        ))}
                    </div>
                ) : (
                    <div className="flex items-center gap-3 p-6 bg-slate-50 dark:bg-slate-800/50 text-slate-500 rounded-3xl border border-dashed border-slate-200 dark:border-slate-700">
                        <AlertCircle size={20} />
                        <p className="text-sm font-medium">Для этого контеста еще не проводились проверки на плагиат.</p>
                    </div>
                )}
            </div>
        </div>
    );
};