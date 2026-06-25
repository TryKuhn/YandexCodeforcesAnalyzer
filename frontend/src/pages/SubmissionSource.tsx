import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {ArrowLeft, Code2, User, Clock, CheckCircle2, AlertCircle, Zap, HardDrive, ShieldBan} from 'lucide-react';
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

            <div className="bg-white dark:bg-slate-900 p-4 sm:p-6 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm">
                <div className="flex flex-wrap gap-4 sm:gap-6 items-start">
                    <div className={`p-3 rounded-2xl shrink-0 ${sub.banned ? 'bg-purple-100 text-purple-600' : sub.verdict === 'OK' ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'}`}>
                        {sub.banned ? <ShieldBan size={28}/> : sub.verdict === 'OK' ? <CheckCircle2 size={28}/> : <AlertCircle size={28}/>}
                    </div>

                    <div className="space-y-0.5 min-w-0">
                        <p className="text-xs text-slate-400 uppercase font-bold tracking-wider">Задача</p>
                        <h2 className="text-base sm:text-xl font-bold dark:text-white truncate">{sub.task_name}</h2>
                    </div>

                    <div className="space-y-0.5">
                        <p className="text-xs text-slate-400 uppercase font-bold tracking-wider">Участник</p>
                        <div className="flex items-center gap-2 dark:text-white font-medium text-sm">
                            <User size={14} className="text-blue-500" /> {sub.participant_login}
                        </div>
                    </div>

                    <div className="space-y-0.5">
                        <p className="text-xs text-slate-400 uppercase font-bold tracking-wider">Язык</p>
                        <div className="flex items-center gap-2 text-slate-500 text-sm">
                            <Code2 size={14} /> {sub.language}
                        </div>
                        <div className="flex items-center gap-1 text-slate-400 text-xs">
                            <Clock size={12} /> {new Date(sub.send_time).toLocaleString()}
                        </div>
                    </div>

                    <div className="flex items-center gap-3 bg-slate-50 dark:bg-slate-800 px-4 py-3 rounded-2xl flex-wrap">
                        <div className="text-center">
                            <p className="text-[10px] text-slate-400 uppercase font-bold">Баллы</p>
                            <p className={`text-lg font-bold ${sub.banned ? 'text-purple-500' : 'text-blue-600'}`}>{sub.banned ? 0 : sub.score}</p>
                        </div>
                        {sub.banned && (
                            <div className="text-center border-l dark:border-slate-700 pl-3">
                                <span className="text-xs font-bold text-purple-500 bg-purple-50 dark:bg-purple-900/20 px-2 py-1 rounded-lg">BANNED</span>
                            </div>
                        )}
                        <div className="text-center border-l dark:border-slate-700 pl-3">
                            <p className="text-[10px] text-slate-400 uppercase font-bold mb-1">Время</p>
                            <p className="text-sm font-bold dark:text-white flex items-center gap-1">
                                <Zap size={12} className="text-amber-500"/>
                                {formatRunTime(sub.run_time)}
                            </p>
                        </div>
                        <div className="text-center border-l dark:border-slate-700 pl-3">
                            <p className="text-[10px] text-slate-400 uppercase font-bold mb-1">Память</p>
                            <p className="text-sm font-bold dark:text-white flex items-center gap-1">
                                <HardDrive size={12} className="text-blue-400"/>
                                {formatMemory(sub.memory_bytes)}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            <div className="bg-slate-950 rounded-3xl border border-slate-800 overflow-hidden shadow-2xl">
                <div className="bg-slate-900 px-4 sm:px-6 py-3 border-b border-slate-800 flex justify-between items-center gap-2">
                    <span className="text-xs font-mono text-slate-500 uppercase">source_code.{sub.language.includes('C++') ? 'cpp' : 'py'}</span>
                    <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-red-500/20"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-amber-500/20"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-green-500/20"></div>
                    </div>
                </div>
                <div className="p-4 sm:p-8 overflow-x-auto">
                    <pre className="font-mono text-xs sm:text-sm text-slate-300 leading-relaxed selection:bg-blue-500/30">
                        <code>{sub.source}</code>
                    </pre>
                </div>
            </div>
        </div>
    );
};
