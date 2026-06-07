// pages/tasks/tabs/PackagesTab.tsx

import { useState, useEffect, useRef } from 'react';
import {
    Loader2, Package, CheckCircle, XCircle, AlertCircle,
    Play, Download
} from 'lucide-react';
import { api } from '../../../api/instance';

interface Props {
    polygonId: number;
}

interface PolygonPackage {
    id: number;
    revision: number;
    creationTimeSeconds: number;
    state: 'PENDING' | 'RUNNING' | 'READY' | 'FAILED';
    comment?: string;
    type: string;
}

const STATE_CONFIG: Record<PolygonPackage['state'], {
    label: string;
    color: string;
    bg: string;
    icon: React.ReactNode;
}> = {
    PENDING: {
        label: 'В очереди',
        color: 'text-yellow-700 dark:text-yellow-400',
        bg: 'bg-yellow-100 dark:bg-yellow-900/30',
        icon: <Loader2 size={12} className="animate-spin" />,
    },
    RUNNING: {
        label: 'Сборка',
        color: 'text-blue-700 dark:text-blue-400',
        bg: 'bg-blue-100 dark:bg-blue-900/30',
        icon: <Loader2 size={12} className="animate-spin" />,
    },
    READY: {
        label: 'Готов',
        color: 'text-green-700 dark:text-green-400',
        bg: 'bg-green-100 dark:bg-green-900/30',
        icon: <CheckCircle size={12} />,
    },
    FAILED: {
        label: 'Ошибка',
        color: 'text-red-700 dark:text-red-400',
        bg: 'bg-red-100 dark:bg-red-900/30',
        icon: <XCircle size={12} />,
    },
};

const formatTime = (seconds: number) => {
    const date = new Date(seconds * 1000);
    return date.toLocaleString('ru-RU', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
};

export const PackagesTab = ({ polygonId }: Props) => {
    const [packages, setPackages] = useState<PolygonPackage[]>([]);
    const [loading, setLoading] = useState(true);
    const [building, setBuilding] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [buildSuccess, setBuildSuccess] = useState(false);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const hasPending = packages.some(p => p.state === 'PENDING' || p.state === 'RUNNING');

    const load = async (silent = false) => {
        if (!silent) setLoading(true);
        try {
            const res = await api.get(`/polygon/problems/${polygonId}/packages`);
            const pkgs: PolygonPackage[] = res.data || [];
            setPackages(pkgs);
            const stillPending = pkgs.some(p => p.state === 'PENDING' || p.state === 'RUNNING');
            if (!stillPending && pollRef.current) {
                clearInterval(pollRef.current);
                pollRef.current = null;
            }
        } catch (e: any) {
            if (!silent) setError(e?.response?.data?.detail || 'Ошибка загрузки пакетов');
        } finally {
            if (!silent) setLoading(false);
        }
    };

    useEffect(() => {
        load();
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [polygonId]);

    useEffect(() => {
        if (hasPending && !pollRef.current) {
            pollRef.current = setInterval(() => load(true), 5000);
        } else if (!hasPending && pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    }, [hasPending]);

    const handleBuild = async () => {
        setBuilding(true);
        setError(null);
        setBuildSuccess(false);
        try {
            await api.post(`/polygon/problems/${polygonId}/packages/build`);
            setBuildSuccess(true);
            setTimeout(() => setBuildSuccess(false), 3000);
            await load();
            if (!pollRef.current) {
                pollRef.current = setInterval(() => load(true), 5000);
            }
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка запуска сборки');
        } finally {
            setBuilding(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <Loader2 size={28} className="animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <div className="p-4 lg:p-6 space-y-4 max-w-3xl mx-auto">
            {/* Toolbar */}
            <div className="flex items-center gap-3 flex-wrap">
                <span className="text-sm font-bold text-slate-700 dark:text-slate-200 flex-1">
                    Пакеты ({packages.length})
                </span>
                {hasPending && (
                    <span className="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400">
                        <Loader2 size={12} className="animate-spin" />
                        Обновление...
                    </span>
                )}
                {buildSuccess && (
                    <span className="text-xs text-green-600 dark:text-green-400 font-bold">Сборка запущена</span>
                )}
                <button
                    onClick={handleBuild}
                    disabled={building}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold
                               bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50
                               shadow-lg shadow-blue-500/20"
                >
                    {building ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
                    Собрать пакет
                </button>
            </div>

            {error && (
                <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-xl text-sm">
                    <AlertCircle size={16} />
                    {error}
                </div>
            )}

            {packages.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                    <Package size={48} className="mb-3 opacity-10" />
                    <p className="font-bold">Нет пакетов</p>
                    <p className="text-xs mt-1">Нажмите «Собрать пакет» для создания</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {packages.map(pkg => {
                        const stateConf = STATE_CONFIG[pkg.state];
                        return (
                            <div
                                key={pkg.id}
                                className="border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3
                                           bg-white dark:bg-slate-900"
                            >
                                <div className="flex items-center gap-3 flex-wrap">
                                    <span className="text-xs font-mono text-slate-500 shrink-0">#{pkg.id}</span>

                                    <span className="text-sm font-bold text-slate-700 dark:text-slate-200 flex-1 min-w-0 truncate">
                                        rev. {pkg.revision} &mdash; {pkg.type}
                                    </span>

                                    <span className={`flex items-center gap-1.5 text-[11px] font-bold px-2 py-0.5 rounded-full shrink-0 ${stateConf.color} ${stateConf.bg}`}>
                                        {stateConf.icon}
                                        {stateConf.label}
                                    </span>

                                    {pkg.state === 'READY' ? (
                                        <div
                                            title="Скачивание пакетов в разработке"
                                            className="flex items-center gap-1 text-[11px] font-bold px-2 py-1 rounded-lg
                                                       bg-slate-100 dark:bg-slate-800 text-slate-400 cursor-not-allowed shrink-0"
                                        >
                                            <Download size={11} />
                                            Скачать
                                        </div>
                                    ) : null}
                                </div>

                                <div className="flex items-center gap-4 mt-1.5 flex-wrap">
                                    <span className="text-[11px] text-slate-400">
                                        {formatTime(pkg.creationTimeSeconds)}
                                    </span>
                                    {pkg.comment && (
                                        <span className="text-[11px] text-slate-500 italic truncate max-w-xs">
                                            {pkg.comment}
                                        </span>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};
