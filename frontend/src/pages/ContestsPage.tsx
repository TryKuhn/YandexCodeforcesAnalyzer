import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Trophy, Plus, ExternalLink,
    RefreshCw, Loader2, Trash2
} from 'lucide-react';
import { api } from '../api/instance';

export const ContestsPage = () => {
    const navigate = useNavigate();
    const [contests, setContests] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [syncingId, setSyncingId] = useState<number | null>(null);

    const [unofficialMap, setUnofficialMap] = useState<Record<number, boolean>>({});

    useEffect(() => {
        fetchContests();
    }, []);

    const fetchContests = async () => {
        try {
            const res = await api.get('/contests/list');
            const data = res.data;
            setContests(data);

            const initialMap: Record<number, boolean> = {};
            data.forEach((contest: any) => {
                initialMap[contest.id] = contest.unofficial ?? true;
            });
            setUnofficialMap(initialMap);
        } catch (e) {
            console.error(e);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSync = async (contest: any) => {
        setSyncingId(contest.id);
        const isUnofficial = unofficialMap[contest.id] ?? true;

        try {
            const endpoint = contest.platform === 'cf' ? '/codeforces/standings' : '/yandex/standings';
            await api.post(endpoint, {
                contest_id: contest.external_id,
                as_manager: true,
                from_pos: 1,
                count: 100,
                show_unofficial: isUnofficial
            });
            alert(`Данные контеста "${contest.name}" обновлены (${isUnofficial ? 'с неофициальными' : 'только официальные'})`);
            fetchContests();
        } catch (e) {
            alert('Ошибка синхронизации');
        } finally {
            setSyncingId(null);
        }
    };

    const handleToggleAndSync = async (contest: any) => {
        const currentVal = unofficialMap[contest.id] ?? contest.unofficial ?? true;
        const newVal = !currentVal;

        setUnofficialMap(prev => ({ ...prev, [contest.id]: newVal }));

        setSyncingId(contest.id);
        try {
            const endpoint = contest.platform === 'cf' ? '/codeforces/standings' : '/yandex/standings';
            await api.post(endpoint, {
                contest_id: contest.external_id,
                as_manager: true,
                from_pos: 1,
                count: 100,
                show_unofficial: newVal
            });

            await fetchContests();
        } catch (e) {
            console.error(e);
            alert('Не удалось обновить результаты');
            setUnofficialMap(prev => ({ ...prev, [contest.id]: currentVal }));
        } finally {
            setSyncingId(null);
        }
    };


    const handleDelete = async (contestId: number, name: string) => {
        if (!confirm(`Вы уверены, что хотите удалить контест "${name}"? Все результаты и посылки будут стерты.`)) return;

        try {
            await api.delete(`/contests/${contestId}`);
            setContests(contests.filter(c => c.id !== contestId));
        } catch (e) {
            alert('Ошибка при удалении');
        }
    };

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-slate-200">Мои контесты</h1>
                <button onClick={() => navigate('/contests/sync')} className="bg-blue-600 text-slate-200 px-4 sm:px-5 py-2 sm:py-2.5 rounded-xl font-bold flex items-center gap-2 hover:bg-blue-700 transition-all text-sm sm:text-base shrink-0">
                    <Plus size={18} /> Загрузить новый
                </button>
            </div>

            {isLoading ? (
                <div className="py-20 text-center"><RefreshCw className="animate-spin inline text-blue-600" /></div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {contests.map((contest) => (
                        <div key={contest.id} className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 flex flex-col group relative">
                            <button
                                onClick={() => handleDelete(contest.id, contest.name)}
                                className="absolute top-4 right-4 p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                            >
                                <Trash2 size={18} />
                            </button>

                            <div className="flex justify-between items-start mb-4">
                                <div className={`p-3 rounded-2xl ${contest.platform === 'cf' ? 'bg-orange-100 text-orange-600' : 'bg-red-100 text-red-600'}`}>
                                    <Trophy size={24} />
                                </div>

                                {syncingId === contest.id && (
                                    <div className="flex items-center gap-2 text-blue-600 animate-pulse">
                                        <Loader2 size={16} className="animate-spin" />
                                        <span className="text-[10px] font-bold uppercase">Обновление...</span>
                                    </div>
                                )}
                            </div>

                            <h3 className="font-bold text-lg dark:text-slate-200 line-clamp-2 mb-4 pr-8">{contest.name}</h3>

                            <div className="mt-auto pt-4 border-t border-slate-100 dark:border-slate-800">
                                <div className="flex items-center justify-between mb-4">
                                    <label className={`flex items-center gap-2 cursor-pointer group/label ${syncingId === contest.id ? 'opacity-50 pointer-events-none' : ''}`}>
                                        <input
                                            type="checkbox"
                                            checked={unofficialMap[contest.id] ?? contest.unofficial ?? true}
                                            onChange={() => handleToggleAndSync(contest)}
                                            className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 transition-all"
                                        />
                                        <span className="text-xs text-slate-500 dark:text-slate-400 group-hover/label:text-blue-600 transition-colors font-medium">
                                        Неофициальные
                                    </span>
                                    </label>

                                    <button
                                        onClick={() => handleSync(contest)}
                                        disabled={syncingId === contest.id}
                                        className="p-1.5 text-slate-400 hover:text-blue-600 rounded-lg transition-colors"
                                    >
                                        <RefreshCw size={14} className={syncingId === contest.id ? "animate-spin" : ""} />
                                    </button>
                                </div>

                                <button onClick={() => navigate(`/contests/${contest.id}`)} className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-bold hover:from-violet-700 hover:to-fuchsia-700 shadow-lg shadow-violet-500/25 transition-all">
                                    <span>Войти в соревнование</span>
                                    <ExternalLink size={16} />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
