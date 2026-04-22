import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ShieldCheck, ArrowLeft, Settings2, Zap, AlertCircle } from 'lucide-react';
import { api } from '../api/instance';

export const PlagiarismSetup = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);

    const [config, setConfig] = useState({
        threshold: 70,
        onlyOk: true
    });

    const startCheck = async () => {
        setLoading(true);
        try {
            // Передаем порог как дробь 0.7 для C++, либо как 70 — как настроен бек
            const res = await api.post(`/analytics/contests/${id}/check`, {
                threshold: config.threshold / 100,
                onlyOk: config.onlyOk
            });
            // Переходим на страницу отчета (report_id берем из ответа бека)
            navigate(`/contests/${id}/analytics/reports/${res.data.report_id}`);
        } catch (e) {
            alert("Ошибка при запуске анализа");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto space-y-6 animate-in slide-in-from-bottom-4">
            <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-slate-500 hover:text-blue-600 transition-colors font-medium">
                <ArrowLeft size={20} /> Назад
            </button>

            <div className="bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm">
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
                    {/* Слайдер порога */}
                    <div className="space-y-4">
                        <div className="flex justify-between items-center">
                            <label className="font-bold dark:text-slate-300">Порог схожести: {config.threshold}%</label>
                            <span className="text-[10px] uppercase font-black text-blue-500 bg-blue-50 dark:bg-blue-900/20 px-2 py-1 rounded">Рекомендуется 70%+</span>
                        </div>
                        <input
                            type="range" min="10" max="100" step="5"
                            className="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-600"
                            value={config.threshold}
                            onChange={(e) => setConfig({...config, threshold: parseInt(e.target.value)})}
                        />
                    </div>

                    {/* Переключатель Only OK */}
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
                                onChange={(e) => setConfig({...config, onlyOk: e.target.checked})}
                            />
                        </label>
                    </div>

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
