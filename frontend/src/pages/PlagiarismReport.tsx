import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Loader2, AlertTriangle, User, ChevronRight, CheckCircle2 } from 'lucide-react';
import { api } from '../api/instance';

export const PlagiarismReport = () => {
    const { id, reportId } = useParams();
    const navigate = useNavigate();
    const [status, setStatus] = useState<'processing' | 'completed' | 'failed'>('processing');
    const [pairs, setPairs] = useState<any[]>([]);

    useEffect(() => {
        let interval: any;

        const checkStatus = async () => {
            try {
                const res = await api.get(`/analytics/reports/${reportId}`);
                if (res.data.status === 'completed') {
                    setStatus('completed');
                    setPairs(res.data.pairs);
                    clearInterval(interval);
                } else if (res.data.status === 'failed') {
                    setStatus('failed');
                    clearInterval(interval);
                }
            } catch (e) {
                setStatus('failed');
                clearInterval(interval);
            }
        };

        interval = setInterval(checkStatus, 2000);
        checkStatus();

        return () => clearInterval(interval);
    }, [reportId]);

    if (status === 'processing') {
        return (
            <div className="h-100 flex flex-col items-center justify-center space-y-4 bg-white dark:bg-slate-900 rounded-3xl border border-dashed border-slate-200 dark:border-slate-800">
                <Loader2 size={48} className="animate-spin text-blue-600" />
                <div className="text-center">
                    <h2 className="text-xl font-bold dark:text-white">Анализ в процессе...</h2>
                    <p className="text-slate-500 text-sm mt-1">Сравниваем AST-деревья и токены решений</p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold dark:text-white flex items-center gap-3">
                    <AlertTriangle className="text-amber-500" /> Подозрительные пары
                </h1>
                <div className="flex items-center gap-2 text-xs font-bold text-slate-400 bg-slate-100 dark:bg-slate-800 px-3 py-1.5 rounded-full">
                    <CheckCircle2 size={14} className="text-green-500" /> АНАЛИЗ ЗАВЕРШЕН
                </div>
            </div>

            <div className="grid grid-cols-1 gap-3">
                {pairs.map((pair) => (
                    <button
                        key={pair.id}
                        onClick={() => navigate(`/contests/${id}/analytics/compare/${pair.id}`)}
                        className="w-full bg-white dark:bg-slate-900 p-5 rounded-3xl border border-slate-100 dark:border-slate-800 flex items-center justify-between hover:border-blue-500/50 hover:shadow-lg transition-all group"
                    >
                        <div className="flex items-center gap-8">
                            {/* Процент схожести */}
                            <div className="text-center w-16">
                                <div className={`text-2xl font-black ${pair.percent > 90 ? 'text-red-600' : 'text-orange-500'}`}>
                                    {pair.percent}%
                                </div>
                                <div className="text-[10px] font-bold text-slate-400 uppercase">Match</div>
                            </div>

                            {/* Информация об участниках */}
                            <div className="flex items-center gap-6">
                                <div className="text-left">
                                    <p className="text-xs text-slate-400 font-bold mb-1">УЧАСТНИК 1</p>
                                    <div className="flex items-center gap-2 text-sm font-bold dark:text-white">
                                        <User size={14} className="text-blue-500" /> {pair.user1}
                                    </div>
                                </div>
                                <div className="h-10 w-px bg-slate-100 dark:bg-slate-800"></div>
                                <div className="text-left">
                                    <p className="text-xs text-slate-400 font-bold mb-1">УЧАСТНИК 2</p>
                                    <div className="flex items-center gap-2 text-sm font-bold dark:text-white">
                                        <User size={14} className="text-blue-500" /> {pair.user2}
                                    </div>
                                </div>
                            </div>

                            <div className="hidden lg:block px-4 py-2 bg-slate-50 dark:bg-slate-800 rounded-2xl">
                                <p className="text-[10px] text-slate-400 font-bold mb-1 uppercase text-left">Задача</p>
                                <p className="text-xs font-bold dark:text-slate-200">{pair.task_name}</p>
                            </div>
                        </div>

                        <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded-full text-slate-300 group-hover:text-blue-600 transition-colors">
                            <ChevronRight size={20} />
                        </div>
                    </button>
                ))}
            </div>
        </div>
    );
};