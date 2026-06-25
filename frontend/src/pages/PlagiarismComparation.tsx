import {useState, useEffect} from 'react';
import {useParams, useNavigate} from 'react-router-dom';
import {ArrowLeft, Copy, ShieldBan, ShieldCheck} from 'lucide-react';
import {api} from '../api/instance';

export const PlagiarismComparison = () => {
    const {pairId} = useParams();
    const navigate = useNavigate();
    const [data, setData] = useState<any>(null);
    const [banning, setBanning] = useState<1 | 2 | null>(null);
    const [unbanning, setUnbanning] = useState<1 | 2 | null>(null);

    useEffect(() => {
        api.get(`/analytics/pairs/${pairId}`).then(res => setData(res.data));
    }, [pairId]);

    const banSubmission = async (position: 1 | 2) => {
        setBanning(position);
        try {
            await api.post(`/analytics/pairs/${pairId}/ban/${position}`);
            setData((prev: any) => ({
                ...prev,
                ...(position === 1 ? {sub1_banned: true} : {sub2_banned: true}),
            }));
        } catch {
            alert('Ошибка при бане посылки');
        } finally {
            setBanning(null);
        }
    };

    const unbanSubmission = async (position: 1 | 2) => {
        setUnbanning(position);
        try {
            await api.post(`/analytics/pairs/${pairId}/unban/${position}`);
            setData((prev: any) => ({
                ...prev,
                ...(position === 1 ? {sub1_banned: false} : {sub2_banned: false}),
            }));
        } catch {
            alert('Ошибка при разбане посылки');
        } finally {
            setUnbanning(null);
        }
    };

    if (!data) return null;

    const CodeHeader = ({user, userName, subId, banned, position, score}: any) => {
        const displayName = userName || user || 'Неизвестный';
        return (
            <div className={`p-4 border-b dark:border-slate-800 flex flex-wrap items-center justify-between gap-3 ${banned ? 'bg-blue-50 dark:bg-blue-950/40' : 'bg-white dark:bg-slate-900'}`}>
                <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold shrink-0 ${banned ? 'bg-blue-200 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300' : 'bg-blue-100 dark:bg-blue-900/30 text-blue-600'}`}>
                        {displayName[0]?.toUpperCase() || '?'}
                    </div>
                    <div>
                        <div className="flex items-center gap-2 flex-wrap">
                            <p className="font-bold text-sm dark:text-white">{displayName}</p>
                            {banned && <span className="text-[10px] font-black text-blue-600 bg-blue-100 dark:bg-blue-900/40 px-1.5 py-0.5 rounded">ЗАБАНЕН</span>}
                        </div>
                        {userName && <p className="text-xs text-slate-400">{user}</p>}
                        <div className="flex items-center gap-3 mt-0.5">
                            <p className="text-[10px] text-slate-400">ID Посылки: {subId?.split('_').pop() || '—'}</p>
                            {score != null && (
                                <p className="text-[10px] font-bold text-amber-500">
                                    {score} балл{score === 1 ? '' : score < 5 ? 'а' : 'ов'}
                                </p>
                            )}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button onClick={() => navigator.clipboard.writeText(displayName)}
                            className="p-2 text-slate-400 hover:text-blue-500">
                        <Copy size={16}/>
                    </button>
                    {banned ? (
                        <button
                            onClick={() => unbanSubmission(position)}
                            disabled={unbanning !== null}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-200 hover:bg-green-100 dark:bg-slate-700 dark:hover:bg-green-900/40 text-slate-600 dark:text-slate-300 hover:text-green-700 dark:hover:text-green-400 text-xs font-bold rounded-xl transition-colors disabled:opacity-50"
                        >
                            {unbanning === position
                                ? <div className="animate-spin rounded-full h-3 w-3 border border-current/30 border-t-current"/>
                                : <ShieldCheck size={13}/>
                            }
                            Разбанить
                        </button>
                    ) : (
                        <button
                            onClick={() => banSubmission(position)}
                            disabled={banning !== null}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl transition-colors disabled:opacity-50"
                        >
                            {banning === position
                                ? <div className="animate-spin rounded-full h-3 w-3 border border-white/30 border-t-white"/>
                                : <ShieldBan size={13}/>
                            }
                            Забанить
                        </button>
                    )}
                </div>
            </div>
        );
    };

    return (
        <div className="flex flex-col space-y-4 animate-in fade-in duration-300">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <button onClick={() => navigate(-1)}
                        className="flex items-center gap-2 text-slate-500 hover:text-blue-600 transition-colors font-medium">
                    <ArrowLeft size={20}/> К списку пар
                </button>
                <div className="flex items-center gap-3">
                    {data.task_name && (
                        <span className="text-xs font-bold text-slate-500 bg-slate-100 dark:bg-slate-800 dark:text-slate-300 px-3 py-1.5 rounded-xl">
                            Задача: {data.task_name}
                        </span>
                    )}
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-widest hidden sm:block">Similarity:</span>
                    <div className="px-4 py-1.5 bg-red-600 text-white rounded-2xl font-black text-lg shadow-lg shadow-red-500/20">
                        {data.percent}%
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{minHeight: '60vh'}}>
                <div
                    className="flex flex-col rounded-3xl border border-slate-100 dark:border-slate-800 overflow-hidden bg-slate-950">
                    <CodeHeader user={data.user1} userName={data.user1_name} subId={data.sub1_id} banned={data.sub1_banned} position={1} score={data.score1}/>
                    <div className="flex-1 p-4 overflow-auto font-mono text-[11px] leading-relaxed text-slate-300" style={{minHeight: '300px'}}>
                        <pre><code>{data.code1}</code></pre>
                    </div>
                </div>

                <div
                    className="flex flex-col rounded-3xl border border-slate-100 dark:border-slate-800 overflow-hidden bg-slate-950">
                    <CodeHeader user={data.user2} userName={data.user2_name} subId={data.sub2_id} banned={data.sub2_banned} position={2} score={data.score2}/>
                    <div className="flex-1 p-4 overflow-auto font-mono text-[11px] leading-relaxed text-slate-300" style={{minHeight: '300px'}}>
                        <pre><code>{data.code2}</code></pre>
                    </div>
                </div>
            </div>
        </div>
    );
};