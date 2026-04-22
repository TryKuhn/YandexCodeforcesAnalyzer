import {useState, useEffect} from 'react';
import {useParams, useNavigate} from 'react-router-dom';
import {ArrowLeft, RefreshCw, Clock} from 'lucide-react';
import {api} from '../api/instance';

export const ContestViewPage = () => {
    const {id} = useParams();
    const navigate = useNavigate();
    const [data, setData] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setIsLoading(true);
        api.get(`/contests/${id}/table`)
            .then(res => setData(res.data))
            .catch(err => setError(err.response?.data?.detail || "Ошибка загрузки"))
            .finally(() => setIsLoading(false));
    }, [id]);

    const getTextColor = (res: any) => {
        if (res.verdict === 'OK') return 'text-green-500';
        if (res.verdict === 'PARTIAL') return 'text-yellow-500';
        // Красный если: вердикт WA ИЛИ (баллы 0 но попытки > 0)
        if (res.verdict === 'WA' || (res.tries > 0 && res.score === 0)) return 'text-red-500';
        return 'text-slate-300 dark:text-slate-700';
    };

    const formatSubmissionTime = (timeStr: string | null) => {
        if (!timeStr) return null;
        const date = new Date(timeStr);
        return date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    };

    const renderCellContent = (res: any, contestType: string) => {
        // Если вообще нет попыток и баллов - пустота
        if (res.tries === 0 && res.score === 0 && res.verdict === 'NULL') return '';

        if (contestType === 'ICPC') {
            if (res.verdict === 'OK') {
                return res.tries === 0 ? '+' : `+${res.tries}`;
            }
            return res.tries > 0 ? `-${res.tries}` : '';
        }

        // Для IOI: возвращаем баллы. Если баллов 0, но tries > 0,
        // вернет 0, и getTextColor сделает его красным.
        return res.score;
    };

    if (isLoading) return <div className="flex justify-center py-20"><RefreshCw className="animate-spin text-blue-600"
                                                                                size={32}/></div>;
    if (error) return <div className="p-8 text-center text-red-500">{error}</div>;
    if (!data) return null;

    return (
        <div className="space-y-6 animate-in fade-in duration-500 h-full flex flex-col">
            <div className="flex items-center gap-4">
                <button onClick={() => navigate('/contests')}
                        className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors">
                    <ArrowLeft size={24} className="text-slate-500"/>
                </button>
                <div>
                    <h1 className="text-2xl font-bold dark:text-white">{data.contest_name}</h1>
                    <span
                        className="text-[10px] px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded font-bold uppercase">
                        {data.contest_type}
                    </span>
                </div>
            </div>

            <div
                className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm overflow-hidden flex-1">
                <div className="overflow-x-auto w-full custom-scrollbar">
                    <table className="w-full text-left border-collapse min-w-max">
                        <thead>
                        <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-800">
                            <th className="px-6 py-4 font-bold dark:text-white w-16 text-center">#</th>
                            <th className="px-6 py-4 font-bold dark:text-white min-w-[200px]">Участник</th>
                            <th className="px-6 py-4 font-bold dark:text-white text-center w-20 border-l border-slate-100 dark:border-slate-800">Σ</th>
                            {data.tasks.map((task: any, i: number) => (
                                <th key={i} title={task.full_name}
                                    className="px-2 py-4 font-bold text-center dark:text-white border-l border-slate-100 dark:border-slate-800 min-w-[80px]">
                                    {task.short_name}
                                </th>
                            ))}
                        </tr>
                        </thead>
                        <tbody>
                        {data.rows.map((row: any, index: number) => (
                            <tr key={row.id}
                                className="border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                                <td className="px-6 py-4 text-center font-bold text-slate-400 text-xs">{index + 1}</td>
                                <td className="px-6 py-4">
                                    <div className="font-bold dark:text-white text-sm">{row.name}</div>
                                    <div className="text-[10px] text-slate-400 font-mono">@{row.login}</div>
                                </td>
                                <td className="px-4 py-4 text-center font-black text-slate-700 dark:text-slate-300 border-l border-slate-100 dark:border-slate-800">
                                    {row.total_score}
                                </td>
                                {row.results.map((res: any, idx: number) => {
                                    {/* Передаем contest_type для логики +/- */
                                    }
                                    const cellText = renderCellContent(res, data.contest_type);
                                    return (
                                        <td key={idx}
                                            className="px-1 py-2 border-l border-slate-50 dark:border-slate-800/20">
                                            <div className="flex flex-col items-center justify-center min-h-[44px]">
                                                    <span
                                                        className={`font-black text-base leading-tight ${getTextColor(res)}`}>
                                                        {cellText}
                                                    </span>

                                                {/* Для IOI показываем попытки снизу, если баллов > 0 или это красный 0 */}
                                                {data.contest_type !== 'ICPC' && res.tries > 0 && (
                                                    <span className="text-[8px] text-slate-400 uppercase font-bold">
                                                            {res.tries} {res.tries === 1 ? 'try' : 'tries'}
                                                        </span>
                                                )}

                                                {res.time && (
                                                    <div
                                                        className="flex items-center gap-0.5 text-[9px] text-slate-400 opacity-60 mt-0.5 font-mono">
                                                        <Clock size={8}/>
                                                        {formatSubmissionTime(res.time)}
                                                    </div>
                                                )}
                                            </div>
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};
