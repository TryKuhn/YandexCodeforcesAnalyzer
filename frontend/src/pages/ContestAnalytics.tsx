import { useState } from 'react';
import { ShieldAlert, Play, BarChart, AlertCircle } from 'lucide-react';

export const ContestAnalytics = () => {
    const [isRunning, setIsRunning] = useState(false);
    const [report, setReport] = useState<any>(null);

    const runPlagiarism = async () => {
        setIsRunning(true);
        // Здесь будет вызов api.post(`/contests/${id}/plagiarism`)
        setTimeout(() => {
            setIsRunning(false);
            setReport({ suspicious_pairs: 0 }); // Мок
        }, 2000);
    };

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm flex flex-col items-center text-center space-y-4">
                    <div className="p-4 bg-amber-100 text-amber-600 rounded-2xl">
                        <ShieldAlert size={32} />
                    </div>
                    <h3 className="text-xl font-bold dark:text-white">Проверка на плагиат</h3>
                    <p className="text-slate-500 text-sm">Сравнение исходных кодов всех участников по всем задачам.</p>
                    <button
                        onClick={runPlagiarism}
                        disabled={isRunning}
                        className="w-full bg-slate-900 dark:bg-blue-600 text-white py-3 rounded-xl font-bold flex justify-center items-center gap-2 hover:opacity-90 transition-all"
                    >
                        {isRunning ? <div className="animate-spin rounded-full h-5 w-5 border-2 border-white/30 border-t-white" /> : <Play size={18} />}
                        <span>Запустить проверку</span>
                    </button>
                </div>

                <div className="bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm flex flex-col items-center text-center space-y-4">
                    <div className="p-4 bg-blue-100 text-blue-600 rounded-2xl">
                        <BarChart size={32} />
                    </div>
                    <h3 className="text-xl font-bold dark:text-white">Визуальная аналитика</h3>
                    <p className="text-slate-500 text-sm">Графики распределения баллов и сложности задач.</p>
                    <button className="w-full border-2 border-slate-100 dark:border-slate-800 dark:text-white py-3 rounded-xl font-bold hover:bg-slate-50 dark:hover:bg-slate-800 transition-all text-sm">
                        Открыть графики
                    </button>
                </div>
            </div>

            {!report && !isRunning && (
                <div className="flex items-center gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 text-blue-600 rounded-2xl border border-blue-100 dark:border-blue-800/30">
                    <AlertCircle size={20} />
                    <p className="text-xs font-medium">Отчет антиплагиата еще не сформирован для этого контеста.</p>
                </div>
            )}
        </div>
    );
};
