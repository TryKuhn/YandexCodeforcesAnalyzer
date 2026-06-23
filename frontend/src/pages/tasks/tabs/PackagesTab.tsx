// pages/tasks/tabs/PackagesTab.tsx

import { useState, useEffect, useRef } from 'react';
import {
    Loader2, Package, CheckCircle, XCircle, AlertCircle,
    Play, Download, Wrench, Sparkles
} from 'lucide-react';
import { api } from '../../../api/instance';

interface Props {
    polygonId: number;
    sessionId?: string | null;
}

interface AiBuildStatus {
    status: string;          // building | uploading | done | waiting_manual_fix | failed
    current_step?: string;
    error?: string;
}

// Terminal AI build statuses where polling stops.
const TERMINAL = new Set(['done', 'failed', 'waiting_manual_fix']);

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

export const PackagesTab = ({ polygonId, sessionId }: Props) => {
    const [packages, setPackages] = useState<PolygonPackage[]>([]);
    const [loading, setLoading] = useState(true);
    const [building, setBuilding] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [buildSuccess, setBuildSuccess] = useState(false);
    const [aiBuild, setAiBuild] = useState<AiBuildStatus | null>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const aiPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
            if (aiPollRef.current) clearInterval(aiPollRef.current);
        };
    }, [polygonId]);

    const pollAiProgress = () => {
        if (aiPollRef.current || !sessionId) return;
        aiPollRef.current = setInterval(async () => {
            try {
                const res = await api.get(`/ai/upload-progress/${sessionId}`);
                const s: AiBuildStatus = {
                    status: res.data.status,
                    current_step: res.data.current_step,
                    error: res.data.error,
                };
                setAiBuild(s);
                if (TERMINAL.has(s.status)) {
                    if (aiPollRef.current) { clearInterval(aiPollRef.current); aiPollRef.current = null; }
                    setBuilding(false);
                    load(true);
                }
            } catch {
                // keep polling; transient error
            }
        }, 4000);
    };

    // Resume an AI build/repair already running in the background (started from
    // chat, or still going after a page reload) so its status stays visible.
    useEffect(() => {
        if (!sessionId) return;
        (async () => {
            try {
                const res = await api.get(`/ai/upload-progress/${sessionId}`);
                const st: string = res.data?.status || 'idle';
                if (st === 'idle') return;
                setAiBuild({ status: st, current_step: res.data.current_step, error: res.data.error });
                if (!TERMINAL.has(st)) {
                    setBuilding(true);
                    pollAiProgress();
                }
            } catch { /* ignore */ }
        })();
    }, [sessionId]);

    useEffect(() => {
        if (hasPending && !pollRef.current) {
            pollRef.current = setInterval(() => load(true), 5000);
        } else if (!hasPending && pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    }, [hasPending]);

    // Build with AI auto-repair when a session exists; otherwise a plain Polygon build.
    const handleBuild = async () => {
        setBuilding(true);
        setError(null);
        setBuildSuccess(false);
        setAiBuild(null);
        try {
            if (sessionId) {
                await api.post('/ai/build-with-repair', { session_id: sessionId });
                setAiBuild({ status: 'building', current_step: 'Запуск сборки...' });
                pollAiProgress();
            } else {
                await api.post(`/polygon/problems/${polygonId}/packages/build`);
                setBuildSuccess(true);
                setTimeout(() => setBuildSuccess(false), 3000);
                setBuilding(false);
            }
            await load();
            if (!pollRef.current) {
                pollRef.current = setInterval(() => load(true), 5000);
            }
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка запуска сборки');
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
                    title={sessionId ? 'При ошибке ИИ автоматически чинит файлы (до 3 попыток)' : undefined}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold
                               bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50
                               shadow-lg shadow-blue-500/20"
                >
                    {building ? <Loader2 size={13} className="animate-spin" />
                        : sessionId ? <Sparkles size={13} /> : <Play size={13} />}
                    {sessionId ? 'Собрать (с ИИ-починкой)' : 'Собрать пакет'}
                </button>
            </div>

            {/* AI build / auto-repair status */}
            {aiBuild && (
                <div className={`flex items-start gap-2 p-3 rounded-xl text-sm border
                    ${aiBuild.status === 'done'
                        ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-700 dark:text-green-400'
                        : aiBuild.status === 'waiting_manual_fix' || aiBuild.status === 'failed'
                            ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-600 dark:text-red-400'
                            : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-400'
                    }`}>
                    {aiBuild.status === 'done'
                        ? <CheckCircle size={16} className="shrink-0 mt-0.5" />
                        : aiBuild.status === 'waiting_manual_fix' || aiBuild.status === 'failed'
                            ? <Wrench size={16} className="shrink-0 mt-0.5" />
                            : <Loader2 size={16} className="animate-spin shrink-0 mt-0.5" />}
                    <div className="min-w-0">
                        <p className="font-bold">
                            {aiBuild.status === 'done' ? 'Пакет собран'
                                : aiBuild.status === 'waiting_manual_fix' ? 'Не удалось собрать автоматически'
                                : aiBuild.status === 'failed' ? 'Ошибка сборки'
                                : 'Сборка и авто-починка...'}
                        </p>
                        {aiBuild.current_step && (
                            <p className="text-xs opacity-80 mt-0.5 break-words">{aiBuild.current_step}</p>
                        )}
                        {aiBuild.error && (
                            <p className="text-xs opacity-80 mt-0.5 break-words font-mono">{aiBuild.error}</p>
                        )}
                    </div>
                </div>
            )}

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

                                <div className="mt-1.5">
                                    <span className="text-[11px] text-slate-400">
                                        {formatTime(pkg.creationTimeSeconds)}
                                    </span>
                                    {pkg.comment && (
                                        <p className={`text-[11px] mt-1 whitespace-pre-wrap break-words
                                            ${pkg.state === 'FAILED'
                                                ? 'text-red-500 dark:text-red-400 font-mono bg-red-50 dark:bg-red-900/15 rounded-lg p-2'
                                                : 'text-slate-500 italic'}`}>
                                            {pkg.comment}
                                        </p>
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
