import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {ArrowLeft, Code2, User, Clock, CheckCircle2, AlertCircle, Zap, HardDrive} from 'lucide-react';
import { api } from '../api/instance';

export const SubmissionSource = () => {
    const { id, subId } = useParams();
    const navigate = useNavigate();
    const [sub, setSub] = useState<any>(null);

    useEffect(() => {
        api.get(`/contests/submissions/${subId}/source`).then(res => setSub(res.data));
    }, [subId]);

    if (!sub) return null;

    const formatRunTime = (timeStr: string) => {
        if (!timeStr) return '0 ms';
        // Обычно timedelta приходит в формате 0:00:00.050000
        const parts = timeStr.split(':');
        if (parts.length === 3) {
            const seconds = parseFloat(parts[2]);
            return `${Math.round(seconds * 1000)} ms`;
        }
        return timeStr;
    };

    const formatMemory = (bytesStr: string) => {
        const bytes = parseInt(bytesStr);
        if (isNaN(bytes) || bytes === 0) return '0 KB';
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / 1048576).toFixed(1)} MB`;
    };

    return (
        <div className="space-y-6 animate-in slide-in-from-right-4 duration-300 pb-12">
            <button onClick={() => navigate(`/contests/${id}/submissions`)} className="flex items-center gap-2 text-slate-500 hover:text-blue-600 font-medium">
                <ArrowLeft size={20} /> Назад к списку посылок
            </button>

            {/* Карточка информации */}
            <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm flex flex-wrap gap-8 items-center">
                <div className={`p-4 rounded-2xl ${sub.verdict === 'OK' ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'}`}>
                    {sub.verdict === 'OK' ? <CheckCircle2 size={32}/> : <AlertCircle size={32}/>}
                </div>

                <div className="space-y-1">
                    <p className="text-xs text-slate-400 uppercase font-bold tracking-wider">Задача</p>
                    <h2 className="text-xl font-bold dark:text-white">{sub.task_name}</h2>
                </div>

                <div className="space-y-1">
                    <p className="text-xs text-slate-400 uppercase font-bold tracking-wider">Участник</p>
                    <div className="flex items-center gap-2 dark:text-white font-medium">
                        <User size={16} className="text-blue-500" /> {sub.participant_login}
                    </div>
                </div>

                <div className="space-y-1">
                    <p className="text-xs text-slate-400 uppercase font-bold tracking-wider">Язык / Время отправки</p>
                    <div className="flex items-center gap-2 text-slate-500 text-sm">
                        <Code2 size={16} /> {sub.language}
                        <span className="mx-2">|</span>
                        <Clock size={16} /> {new Date(sub.send_time).toLocaleString()}
                    </div>
                </div>

                <div className="ml-auto flex items-center gap-4 bg-slate-50 dark:bg-slate-800 p-4 rounded-2xl">
                    <div className="text-center">
                        <p className="text-[10px] text-slate-400 uppercase font-bold">Баллы</p>
                        <p className="text-lg font-bold text-blue-600">{sub.score}</p>
                    </div>
                    <div className="text-center border-l dark:border-slate-700 pl-6 pr-2">
                        <p className="text-[10px] text-slate-400 uppercase font-bold mb-1">Время</p>
                        <p className="text-sm font-bold dark:text-white flex items-center justify-center gap-1">
                            <Zap size={14} className="text-amber-500"/>
                            {formatRunTime(sub.run_time)}
                        </p>
                    </div>

                    <div className="text-center border-l dark:border-slate-700 pl-6 pr-2">
                        <p className="text-[10px] text-slate-400 uppercase font-bold mb-1">Память</p>
                        <p className="text-sm font-bold dark:text-white flex items-center justify-center gap-1">
                            <HardDrive size={14} className="text-blue-400"/>
                            {formatMemory(sub.memory_bytes)}
                        </p>
                    </div>
                </div>
            </div>

            {/* Блок кода */}
            <div className="bg-slate-950 rounded-3xl border border-slate-800 overflow-hidden shadow-2xl">
                <div className="bg-slate-900 px-6 py-3 border-b border-slate-800 flex justify-between items-center">
                    <span className="text-xs font-mono text-slate-500 uppercase">source_code.{sub.language.includes('C++') ? 'cpp' : 'py'}</span>
                    <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-red-500/20"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-amber-500/20"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-green-500/20"></div>
                    </div>
                </div>
                <div className="p-8 overflow-x-auto">
                    <pre className="font-mono text-sm text-slate-300 leading-relaxed selection:bg-blue-500/30">
                        <code>{sub.source}</code>
                    </pre>
                </div>
            </div>
        </div>
    );
};
