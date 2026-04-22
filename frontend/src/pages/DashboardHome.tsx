import { Trophy, Users, FileCheck, AlertTriangle, TrendingUp } from 'lucide-react';

const StatCard = ({ title, value, icon: Icon, color, trend }: any) => (
    <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
        <div className="flex justify-between items-start mb-4">
            <div className={`p-3 rounded-xl ${color}`}>
                <Icon size={24} className="text-white" />
            </div>
            {trend && (
                <span className="flex items-center gap-1 text-green-500 text-xs font-bold">
                    <TrendingUp size={14} /> {trend}
                </span>
            )}
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">{title}</p>
        <h3 className="text-2xl font-bold mt-1 dark:text-white">{value}</h3>
    </div>
);

export const DashboardHome = () => {
    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Рабочий стол</h1>
                <p className="text-slate-500 dark:text-slate-400">Краткая сводка по вашим соревнованиям.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard title="Контестов" value="0" icon={Trophy} color="bg-blue-600" trend="+0%" />
                <StatCard title="Участников" value="0" icon={Users} color="bg-purple-600" trend="+0%" />
                <StatCard title="Посылок" value="0" icon={FileCheck} color="bg-emerald-600" trend="+0%" />
                <StatCard title="Плагиат" value="0" icon={AlertTriangle} color="bg-amber-600" />
            </div>

            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-100 dark:border-slate-800 p-8 text-center">
                <div className="max-w-sm mx-auto space-y-4">
                    <div className="w-16 h-16 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center mx-auto">
                        <Trophy size={32} className="text-slate-300" />
                    </div>
                    <h3 className="text-lg font-bold dark:text-white">Пока ничего не загружено</h3>
                    <p className="text-slate-500 text-sm">Начните с загрузки вашего первого соревнования из Codeforces или Yandex Contest.</p>
                    <button className="bg-blue-600 text-white px-6 py-2 rounded-xl font-bold hover:bg-blue-700 transition-all">
                        Загрузить контест
                    </button>
                </div>
            </div>
        </div>
    );
};
