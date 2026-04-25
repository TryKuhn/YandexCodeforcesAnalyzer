import {useState, useEffect} from 'react';
import {useParams, useNavigate} from 'react-router-dom';
import {ArrowLeft, Copy} from 'lucide-react';
import {api} from '../api/instance';

export const PlagiarismComparison = () => {
    const {pairId} = useParams();
    const navigate = useNavigate();
    const [data, setData] = useState<any>(null);

    // Функция декодирования (которую мы обсуждали для base64)
    const decodeCode = (str: string) => {
        try {
            return new TextDecoder('utf-8').decode(Uint8Array.from(atob(str), c => c.charCodeAt(0)));
        } catch (e) {
            return "Ошибка декодирования";
        }
    };

    useEffect(() => {
        api.get(`/analytics/pairs/${pairId}`).then(res => {
            const d = res.data;
            d.code1 = decodeCode(d.code1);
            d.code2 = decodeCode(d.code2);
            setData(d);
        });
    }, [pairId]);

    if (!data) return null;

    const CodeHeader = ({user, subId}: any) => (
        <div className="p-4 bg-white dark:bg-slate-900 border-b dark:border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 text-blue-600 rounded-full flex items-center justify-center font-bold">
                    {user ? user[0].toUpperCase() : '?'}
                </div>
                <div>
                    <p className="font-bold text-sm dark:text-white">{user || 'Неизвестный'}</p>
                    <p className="text-[10px] text-slate-400">ID Посылки: {subId?.split('_').pop() || '—'}</p>
                </div>
            </div>
            <button onClick={() => user && navigator.clipboard.writeText(user)}
                    className="p-2 text-slate-400 hover:text-blue-500">
                <Copy size={16}/>
            </button>
        </div>
    );

    return (
        <div className="h-full flex flex-col space-y-4 animate-in fade-in duration-300">
            <div className="flex justify-between items-center">
                <button onClick={() => navigate(-1)}
                        className="flex items-center gap-2 text-slate-500 hover:text-blue-600 transition-colors font-medium">
                    <ArrowLeft size={20}/> К списку пар
                </button>
                <div className="flex items-center gap-4">
                    <span
                        className="text-xs font-bold text-slate-400 uppercase tracking-widest">Similarity Match:</span>
                    <div
                        className="px-6 py-2 bg-red-600 text-white rounded-2xl font-black text-xl shadow-lg shadow-red-500/20">
                        {data.percent}%
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4 flex-1 min-h-0 overflow-hidden">
                <div
                    className="flex flex-col rounded-3xl border border-slate-100 dark:border-slate-800 overflow-hidden bg-slate-950">
                    <CodeHeader user={data.user1} subId={data.sub1_id}/>
                    <div className="flex-1 p-6 overflow-auto font-mono text-[11px] leading-relaxed text-slate-300">
                        <pre><code>{data.code1}</code></pre>
                    </div>
                </div>

                <div
                    className="flex flex-col rounded-3xl border border-slate-100 dark:border-slate-800 overflow-hidden bg-slate-950">
                    <CodeHeader user={data.user2} subId={data.sub2_id}/>
                    <div className="flex-1 p-6 overflow-auto font-mono text-[11px] leading-relaxed text-slate-300">
                        <pre><code>{data.code2}</code></pre>
                    </div>
                </div>
            </div>
        </div>
    );
};