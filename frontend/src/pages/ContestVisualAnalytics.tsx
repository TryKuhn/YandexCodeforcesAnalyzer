import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
    LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
    XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { Loader2, Clock } from 'lucide-react';
import { api } from '../api/instance';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

const Card = ({ title, children, className = '' }: any) => (
    <div className={`bg-white dark:bg-slate-900 rounded-3xl border border-slate-100 dark:border-slate-800 p-5 ${className}`}>
        {title && <h3 className="font-bold text-sm dark:text-white mb-4">{title}</h3>}
        {children}
    </div>
);

const tooltipStyle = {
    contentStyle: {
        background: 'var(--tooltip-bg, #fff)',
        border: '1px solid #e2e8f0',
        borderRadius: '12px',
        fontSize: '12px',
    },
};

export const ContestVisualAnalytics = () => {
    const { id } = useParams();
    const [data, setData] = useState<any>(null);
    const [selectedTask, setSelectedTask] = useState<string>('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        api.get(`/contests/${id}/visual-analytics`)
            .then(r => {
                setData(r.data);
                if (r.data.tasks?.length > 0) setSelectedTask(r.data.tasks[0]);
            })
            .finally(() => setLoading(false));
    }, [id]);

    if (loading) return (
        <div className="flex justify-center py-20">
            <Loader2 className="animate-spin text-blue-500" size={32} />
        </div>
    );

    if (!data) return null;

    const timelineData = data.submissions_over_time[selectedTask] || [];

    const totalSubs = data.task_stats.reduce((a: number, t: any) => a + t.total, 0);
    const totalOk = data.task_stats.reduce((a: number, t: any) => a + t.ok, 0);

    const verdictData = data.task_stats.map((t: any) => ({
        task: t.task,
        OK: t.ok,
        WA: t.wa,
        TLE: t.tle,
        RE: t.re,
        Прочее: t.other,
    }));

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                    { label: 'Посылок', value: totalSubs, color: 'text-blue-600 bg-blue-50 dark:bg-blue-950/40' },
                    { label: 'Успешных', value: totalOk, color: 'text-green-600 bg-green-50 dark:bg-green-950/40' },
                    { label: 'Задач', value: data.tasks.length, color: 'text-violet-600 bg-violet-50 dark:bg-violet-950/40' },
                    { label: 'Языков', value: data.language_breakdown.length, color: 'text-amber-600 bg-amber-50 dark:bg-amber-950/40' },
                ].map(s => (
                    <div key={s.label} className={`rounded-2xl p-4 ${s.color}`}>
                        <p className="text-2xl font-black">{s.value}</p>
                        <p className="text-xs font-semibold opacity-70 mt-0.5">{s.label}</p>
                    </div>
                ))}
            </div>

            <Card title="Активность по задачам">
                <div className="flex flex-wrap gap-2 mb-4">
                    {data.tasks.map((t: string) => (
                        <button
                            key={t}
                            onClick={() => setSelectedTask(t)}
                            className={`px-3 py-1 rounded-xl text-xs font-bold transition-colors ${
                                selectedTask === t
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-slate-900 dark:hover:text-white'
                            }`}
                        >
                            {t}
                        </button>
                    ))}
                </div>
                {timelineData.length === 0 ? (
                    <p className="text-slate-400 text-sm text-center py-8">Нет данных</p>
                ) : (
                    <ResponsiveContainer width="100%" height={260}>
                        <LineChart data={timelineData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                            <Tooltip {...tooltipStyle} />
                            <Legend wrapperStyle={{ fontSize: 12 }} />
                            <Line type="monotone" dataKey="total" name="Всего" stroke="#3b82f6" strokeWidth={2} dot={false} />
                            <Line type="monotone" dataKey="ok" name="Успешных" stroke="#10b981" strokeWidth={2} dot={false} />
                        </LineChart>
                    </ResponsiveContainer>
                )}
            </Card>

            <Card title="Структура посылок по задачам">
                {verdictData.length === 0 ? (
                    <p className="text-slate-400 text-sm text-center py-8">Нет данных</p>
                ) : (
                    <ResponsiveContainer width="100%" height={Math.max(200, verdictData.length * 40)}>
                        <BarChart data={verdictData} layout="vertical" margin={{ top: 0, right: 10, left: 10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                            <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                            <YAxis type="category" dataKey="task" tick={{ fontSize: 12, fontWeight: 700 }} width={30} />
                            <Tooltip {...tooltipStyle} />
                            <Legend wrapperStyle={{ fontSize: 12 }} />
                            <Bar dataKey="OK" stackId="a" fill="#10b981" radius={[0, 0, 0, 0]} />
                            <Bar dataKey="WA" stackId="a" fill="#ef4444" />
                            <Bar dataKey="TLE" stackId="a" fill="#f59e0b" />
                            <Bar dataKey="RE" stackId="a" fill="#8b5cf6" />
                            <Bar dataKey="Прочее" stackId="a" fill="#94a3b8" radius={[0, 4, 4, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                )}
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card title="Процент сдавших задачу">
                    {data.task_stats.length === 0 ? (
                        <p className="text-slate-400 text-sm text-center py-8">Нет данных</p>
                    ) : (
                        <div className="space-y-3">
                            {[...data.task_stats].sort((a: any, b: any) => b.solve_rate - a.solve_rate).map((t: any) => (
                                <div key={t.task}>
                                    <div className="flex justify-between text-xs font-medium mb-1 gap-2">
                                        <span className="dark:text-white font-bold truncate" title={t.full_name}>
                                            {t.task}
                                            {t.full_name && t.full_name !== t.task &&
                                                <span className="font-normal text-slate-400 ml-1 hidden sm:inline">· {t.full_name}</span>
                                            }
                                        </span>
                                        <span className="text-slate-500 shrink-0">{t.solvers} чел. · {t.solve_rate}%</span>
                                    </div>
                                    <div className="h-3 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                        <div
                                            className="h-full rounded-full transition-all"
                                            style={{
                                                width: `${t.solve_rate}%`,
                                                background: t.solve_rate >= 60
                                                    ? '#10b981'
                                                    : t.solve_rate >= 30
                                                        ? '#f59e0b'
                                                        : '#ef4444',
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </Card>

                <Card title="Распределение баллов">
                    {data.score_distribution.length === 0 ? (
                        <p className="text-slate-400 text-sm text-center py-8">Нет данных о баллах</p>
                    ) : (
                        <ResponsiveContainer width="100%" height={220}>
                            <BarChart data={data.score_distribution} margin={{ top: 5, right: 10, left: -15, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                <XAxis dataKey="range" tick={{ fontSize: 10 }} />
                                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                                <Tooltip {...tooltipStyle} formatter={(v: any) => [v, 'Участников']} />
                                <Bar dataKey="count" name="Участников" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card title="Языки программирования">
                    {data.language_breakdown.length === 0 ? (
                        <p className="text-slate-400 text-sm text-center py-8">Нет данных</p>
                    ) : (
                        <div className="flex items-center gap-4">
                            <ResponsiveContainer width="55%" height={200}>
                                <PieChart>
                                    <Pie
                                        data={data.language_breakdown}
                                        dataKey="count"
                                        nameKey="language"
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={50}
                                        outerRadius={80}
                                        paddingAngle={2}
                                    >
                                        {data.language_breakdown.map((_: any, i: number) => (
                                            <Cell key={i} fill={COLORS[i % COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <Tooltip {...tooltipStyle} formatter={(v: any, n: any) => [v, n]} />
                                </PieChart>
                            </ResponsiveContainer>
                            <div className="flex-1 space-y-1.5 min-w-0">
                                {data.language_breakdown.slice(0, 6).map((l: any, i: number) => (
                                    <div key={l.language} className="flex items-center gap-2 text-xs">
                                        <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                                        <span className="truncate text-slate-600 dark:text-slate-400">{l.language}</span>
                                        <span className="ml-auto font-bold dark:text-white shrink-0">{l.count}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </Card>

                <Card title="Первые сдачи">
                    {data.first_solves.length === 0 ? (
                        <p className="text-slate-400 text-sm text-center py-8">Нет данных</p>
                    ) : (
                        <div className="space-y-2">
                            {data.first_solves.map((fs: any) => (
                                <div key={fs.task} className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                                    <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-white text-[10px] font-black bg-slate-600
                                    `}>
                                        {fs.task}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-xs font-bold dark:text-white truncate">{fs.login}</p>
                                        <p className="text-[10px] text-slate-400 truncate" title={fs.full_name}>
                                            {fs.task}{fs.full_name && fs.full_name !== fs.task ? ` · ${fs.full_name}` : ''}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-1 text-xs text-slate-400 shrink-0">
                                        <Clock size={11} />
                                        {fs.minute < 60
                                            ? `${fs.minute} мин`
                                            : `${Math.floor(fs.minute / 60)}ч ${fs.minute % 60}м`}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </Card>
            </div>
        </div>
    );
};
