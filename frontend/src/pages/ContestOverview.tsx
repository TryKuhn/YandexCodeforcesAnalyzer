import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Users, Trophy, FileCode, Calendar,
    Hash, ArrowRight, BarChart3
} from 'lucide-react';
import { api } from '../api/instance';

const StatCard = ({ title, value, icon: Icon, color }: any) => (
    <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
        <div className="flex justify-between items-start mb-4">
            <div className={`p-3 rounded-xl ${color}`}>
                <Icon size={20} className="text-white" />
            </div>
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">{title}</p>
        <h3 className="text-2xl font-bold mt-1 dark:text-white">{value}</h3>
    </div>
);

export const ContestOverview = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [data, setData] = useState<any>(null);

    useEffect(() => {
        api.get(`/contests/${id}/overview`).then(res => setData(res.data));
    }, [id]);

    if (!data) return null;

    const actionCards = [
        { label: 'Таблица результатов', path: 'table', icon: Trophy, desc: 'Просмотр текущего ранклиста и баллов' },
        { label: 'Все посылки', path: 'submissions', icon: FileCode, desc: 'Поиск и фильтрация решений участников' },
        { label: 'Анализ плагиата', path: 'analytics', icon: BarChart3, desc: 'Запуск проверки кодов на копирование' },
    ];

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            {/* Сводка */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard title="Задач" value={data.stats.tasks} icon={Trophy} color="bg-blue-600" />
                <StatCard title="Участников" value={data.stats.participants} icon={Users} color="bg-purple-600" />
                <StatCard title="Посылок" value={data.stats.submissions} icon={FileCode} color="bg-emerald-600" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="md:col-span-1 space-y-6">
                    <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-100 dark:border-slate-800">
                        <h3 className="font-bold dark:text-white mb-6">Информация</h3>
                        <div className="space-y-4">
                            <div className="flex items-center justify-between text-sm">
                                <div className="flex items-center gap-2 text-slate-500"><Calendar size={16} /> Начало</div>
                                <span className="font-medium dark:text-slate-200">{new Date(data.start_time).toLocaleString()}</span>
                            </div>
                            <div className="flex items-center justify-between text-sm">
                                <div className="flex items-center gap-2 text-slate-500"><Hash size={16} /> External ID</div>
                                <span className="font-mono font-medium dark:text-slate-200">{data.external_id}</span>
                            </div>
                            <div className="flex items-center justify-between text-sm">
                                <div className="flex items-center gap-2 text-slate-500"><Trophy size={16} /> Тип</div>
                                <span className="px-2 py-0.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 rounded text-xs font-bold">{data.type}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="md:col-span-2 space-y-4">
                    <h3 className="font-bold dark:text-white px-2">Быстрые действия</h3>
                    {actionCards.map((card) => (
                        <button
                            key={card.path}
                            onClick={() => navigate(card.path)}
                            className="w-full flex items-center justify-between p-6 bg-white dark:bg-slate-900 rounded-3xl border border-slate-100 dark:border-slate-800 hover:border-blue-500/50 hover:shadow-lg hover:shadow-blue-500/5 transition-all group"
                        >
                            <div className="flex items-center gap-4">
                                <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-2xl text-slate-400 group-hover:text-blue-600 transition-colors">
                                    <card.icon size={24} />
                                </div>
                                <div className="text-left">
                                    <p className="font-bold dark:text-white">{card.label}</p>
                                    <p className="text-xs text-slate-500">{card.desc}</p>
                                </div>
                            </div>
                            <ArrowRight size={20} className="text-slate-300 group-hover:text-blue-600 group-hover:translate-x-1 transition-all" />
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
};
