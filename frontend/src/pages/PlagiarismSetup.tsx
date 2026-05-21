import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ShieldCheck, ArrowLeft, Settings2, Zap, AlertCircle, Code2, ListChecks } from 'lucide-react';
import { api } from '../api/instance';

interface Meta {
    languages: string[];
    tasks: string[];
}

const MultiSelect = ({
    label,
    icon,
    items,
    selected,
    onChange,
}: {
    label: string;
    icon: React.ReactNode;
    items: string[];
    selected: string[];
    onChange: (v: string[]) => void;
}) => {
    const allSelected = selected.length === 0;

    const toggle = (item: string) => {
        if (selected.includes(item)) {
            const next = selected.filter((s) => s !== item);
            onChange(next);
        } else {
            onChange([...selected, item]);
        }
    };

    const selectAll = () => onChange([]);

    return (
        <div className="space-y-3">
            <div className="flex items-center gap-2">
                <div className="p-1.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-lg">
                    {icon}
                </div>
                <span className="font-bold text-sm dark:text-slate-300">{label}</span>
                <button
                    onClick={selectAll}
                    className={`ml-auto text-xs font-semibold px-2 py-0.5 rounded transition-colors ${
                        allSelected
                            ? 'bg-blue-600 text-white'
                            : 'text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20'
                    }`}
                >
                    Все
                </button>
            </div>
            <div className="flex flex-wrap gap-2">
                {items.map((item) => {
                    const active = selected.includes(item);
                    return (
                        <button
                            key={item}
                            onClick={() => toggle(item)}
                            className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                                active
                                    ? 'bg-blue-600 text-white border-blue-600'
                                    : 'bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-blue-400'
                            }`}
                        >
                            {item}
                        </button>
                    );
                })}
            </div>
        </div>
    );
};

export const PlagiarismSetup = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [meta, setMeta] = useState<Meta>({ languages: [], tasks: [] });

    const [config, setConfig] = useState({
        threshold: 70,
        banThreshold: 90,
        onlyOk: true,
        languages: [] as string[],
        tasks: [] as string[],
    });

    useEffect(() => {
        api.get(`/analytics/contests/${id}/submissions/meta`)
            .then((r) => setMeta(r.data))
            .catch(() => {});
    }, [id]);

    const startCheck = async () => {
        setLoading(true);
        try {
            const res = await api.post(`/analytics/contests/${id}/check`, {
                threshold: config.threshold / 100,
                banThreshold: config.banThreshold / 100,
                onlyOk: config.onlyOk,
                languages: config.languages.length > 0 ? config.languages : null,
                tasks: config.tasks.length > 0 ? config.tasks : null,
            });
            navigate(`/contests/${id}/analytics/reports/${res.data.reportId}`);
        } catch (e) {
            alert('Ошибка при запуске анализа');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto space-y-6 animate-in slide-in-from-bottom-4">
            <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-slate-500 hover:text-blue-600 transition-colors font-medium">
                <ArrowLeft size={20} /> Назад
            </button>

            <div className="bg-white dark:bg-slate-900 p-5 sm:p-8 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm">
                <div className="flex items-center gap-4 mb-8">
                    <div className="p-3 bg-blue-600 rounded-2xl text-white shadow-lg shadow-blue-500/20">
                        <Settings2 size={24} />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold dark:text-white">Параметры проверки</h1>
                        <p className="text-slate-500 text-sm font-medium">Настройте алгоритм сравнения кодов</p>
                    </div>
                </div>

                <div className="space-y-8">
                    <div className="space-y-6">
                        <div className="space-y-3">
                            <div className="flex justify-between items-center">
                                <label className="font-bold dark:text-slate-300">Порог отображения: {config.threshold}%</label>
                                <span className="text-[10px] uppercase font-black text-blue-500 bg-blue-50 dark:bg-blue-900/20 px-2 py-1 rounded">Показывать подозрительные</span>
                            </div>
                            <input
                                type="range" min="10" max="100" step="5"
                                className="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-600"
                                value={config.threshold}
                                onChange={(e) => {
                                    const v = parseInt(e.target.value);
                                    setConfig({ ...config, threshold: v, banThreshold: Math.max(config.banThreshold, v) });
                                }}
                            />
                            <p className="text-xs text-slate-400">Пары с совпадением ≥ этого порога будут показаны в отчёте для ручной проверки.</p>
                        </div>

                        <div className="space-y-3">
                            <div className="flex justify-between items-center">
                                <label className="font-bold dark:text-slate-300">Порог автобана: {config.banThreshold}%</label>
                                <span className="text-[10px] uppercase font-black text-red-500 bg-red-50 dark:bg-red-900/20 px-2 py-1 rounded">Бан автоматически</span>
                            </div>
                            <input
                                type="range" min="10" max="100" step="5"
                                className="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-red-500"
                                value={config.banThreshold}
                                onChange={(e) => {
                                    const v = parseInt(e.target.value);
                                    setConfig({ ...config, banThreshold: v, threshold: Math.min(config.threshold, v) });
                                }}
                            />
                            <p className="text-xs text-slate-400">Пары с совпадением ≥ этого порога получат 0 баллов автоматически. Должен быть ≥ порога отображения.</p>
                        </div>
                    </div>

                    <div className="space-y-3">
                        <label className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-all border border-transparent hover:border-slate-200 dark:hover:border-slate-700">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-green-100 dark:bg-green-900/30 text-green-600 rounded-xl">
                                    <ShieldCheck size={20} />
                                </div>
                                <div>
                                    <p className="font-bold text-sm dark:text-white">Только успешные решения</p>
                                    <p className="text-xs text-slate-500">Игнорировать посылки с WA, TL, RE и т.д.</p>
                                </div>
                            </div>
                            <input
                                type="checkbox"
                                className="w-6 h-6 rounded-lg border-none bg-slate-200 dark:bg-slate-700 text-blue-600 focus:ring-0"
                                checked={config.onlyOk}
                                onChange={(e) => setConfig({ ...config, onlyOk: e.target.checked })}
                            />
                        </label>
                    </div>

                    {meta.languages.length > 0 && (
                        <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-800">
                            <MultiSelect
                                label="Языки программирования"
                                icon={<Code2 size={16} />}
                                items={meta.languages}
                                selected={config.languages}
                                onChange={(v) => setConfig({ ...config, languages: v })}
                            />
                        </div>
                    )}

                    {meta.tasks.length > 0 && (
                        <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-800">
                            <MultiSelect
                                label="Задачи"
                                icon={<ListChecks size={16} />}
                                items={meta.tasks}
                                selected={config.tasks}
                                onChange={(v) => setConfig({ ...config, tasks: v })}
                            />
                        </div>
                    )}

                    <div className="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-2xl border border-amber-100 dark:border-amber-800/30 flex gap-3">
                        <AlertCircle className="text-amber-600 shrink-0" size={20} />
                        <p className="text-xs text-amber-700 dark:text-amber-500 leading-relaxed">
                            Анализ выполняется на стороне C++ модуля с использованием LSH-хэширования.
                            Процесс может занять время в зависимости от количества посылок.
                        </p>
                    </div>

                    <button
                        onClick={startCheck}
                        disabled={loading}
                        className="w-full bg-slate-900 dark:bg-blue-600 text-white py-4 rounded-2xl font-bold flex justify-center items-center gap-3 hover:opacity-90 transition-all shadow-xl shadow-blue-500/10 disabled:opacity-50"
                    >
                        {loading ? <div className="animate-spin rounded-full h-5 w-5 border-2 border-white/30 border-t-white" /> : <Zap size={20} />}
                        <span>Запустить процесс анализа</span>
                    </button>
                </div>
            </div>
        </div>
    );
};
