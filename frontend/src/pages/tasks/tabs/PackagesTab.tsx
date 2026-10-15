// pages/tasks/tabs/PackagesTab.tsx

import { useCallback, useEffect, useRef, useState } from 'react';
import {
    Loader2, Package, CheckCircle, XCircle, AlertCircle, Download, Wrench, Sparkles, Upload, History,
} from 'lucide-react';
import { api } from '../../../api/instance';
import { aiApi, errorText, isActive, isBuildFinal, type AiBuild, type AiRun } from '../../../api/ai';
import { EjudgeExportModal } from '../components/EjudgeExportModal';

interface Props {
    polygonId: number;
    sessionId?: string | null;
    latestBuild?: AiBuild | null;
    activeRun?: AiRun | null;
    onRunStarted?: (run: AiRun) => void;
}

interface PolygonPackage {
    id: number;
    revision: number;
    creationTimeSeconds: number;
    state: 'PENDING' | 'RUNNING' | 'READY' | 'FAILED';
    comment?: string;
    type: string;
}

const STATE_CONFIG: Record<PolygonPackage['state'], { label: string; color: string; bg: string; icon: React.ReactNode }> = {
    PENDING: {
        label: 'В очереди', color: 'text-yellow-700 dark:text-yellow-400', bg: 'bg-yellow-100 dark:bg-yellow-900/30',
        icon: <Loader2 size={12} className="animate-spin" />,
    },
    RUNNING: {
        label: 'Сборка', color: 'text-blue-700 dark:text-blue-400', bg: 'bg-blue-100 dark:bg-blue-900/30',
        icon: <Loader2 size={12} className="animate-spin" />,
    },
    READY: {
        label: 'Готов', color: 'text-green-700 dark:text-green-400', bg: 'bg-green-100 dark:bg-green-900/30',
        icon: <CheckCircle size={12} />,
    },
    FAILED: {
        label: 'Ошибка', color: 'text-red-700 dark:text-red-400', bg: 'bg-red-100 dark:bg-red-900/30',
        icon: <XCircle size={12} />,
    },
};

const DOWNLOAD_TYPES = ['standard', 'linux', 'windows'] as const;

const formatTime = (seconds: number) => new Date(seconds * 1000).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
});

export const PackagesTab = ({ polygonId, sessionId, latestBuild, activeRun, onRunStarted }: Props) => {
    const [packages, setPackages] = useState<PolygonPackage[]>([]);
    const [builds, setBuilds] = useState<AiBuild[]>([]);
    const [loading, setLoading] = useState(true);
    const [starting, setStarting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [downloading, setDownloading] = useState<string | null>(null);
    const [exportPackage, setExportPackage] = useState<number | null>(null);

    const building = isActive(activeRun) && activeRun?.kind === 'build';
    const hasPending = packages.some(p => p.state === 'PENDING' || p.state === 'RUNNING');

    const load = useCallback(async (silent = false) => {
        if (!silent) setLoading(true);
        try {
            const [pkgs, history] = await Promise.all([
                api.get<PolygonPackage[]>(`/polygon/problems/${polygonId}/packages`),
                sessionId ? aiApi.builds(sessionId, 10) : Promise.resolve([] as AiBuild[]),
            ]);
            setPackages([...(pkgs.data || [])].sort((a, b) => b.id - a.id));
            setBuilds(history);
        } catch (e) {
            if (!silent) setError(errorText(e, 'Ошибка загрузки пакетов'));
        } finally {
            if (!silent) setLoading(false);
        }
    }, [polygonId, sessionId]);

    useEffect(() => { load(); }, [load]);

    // follow builds (ours or started in Polygon) while something is in progress
    useEffect(() => {
        if (!hasPending && !building) return;
        const timer = setInterval(() => load(true), 5000);
        return () => clearInterval(timer);
    }, [hasPending, building, load]);

    // the latest build changed (e.g. a repair attempt): refresh the lists
    // (not on mount: the effect above already loads them)
    const buildKey = `${latestBuild?.id ?? ''}:${latestBuild?.state ?? ''}`;
    const seenBuildKey = useRef(buildKey);
    useEffect(() => {
        if (seenBuildKey.current === buildKey) return;
        seenBuildKey.current = buildKey;
        load(true);
    }, [buildKey, load]);

    const handleBuild = async () => {
        setStarting(true);
        setError(null);
        try {
            if (sessionId) {
                const { run } = await aiApi.build(sessionId);
                onRunStarted?.(run);
            } else {
                await api.post(`/polygon/problems/${polygonId}/packages/build`);
            }
            await load(true);
        } catch (e) {
            setError(errorText(e, 'Ошибка запуска сборки'));
        } finally {
            setStarting(false);
        }
    };

    const download = async (pkg: PolygonPackage, type: string) => {
        setDownloading(`${pkg.id}-${type}`);
        try {
            const res = await api.get(`/polygon/problems/${polygonId}/packages/${pkg.id}/download`, {
                params: { type }, responseType: 'blob',
            });
            const url = URL.createObjectURL(res.data as Blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `problem-${polygonId}-${pkg.id}-${type}.zip`;
            a.style.display = 'none';
            document.body.appendChild(a);  // Firefox ignores clicks on detached links
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 10000);  // let the download start first
        } catch (e) {
            setError(errorText(e, 'Не удалось скачать пакет'));
        } finally {
            setDownloading(null);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <Loader2 size={28} className="animate-spin text-blue-500" />
            </div>
        );
    }

    const lastFailed = latestBuild && ['FAILED', 'TIMEOUT', 'ERROR'].includes(latestBuild.state);
    const lastReady = latestBuild?.state === 'READY';
    // not final, but no build run is active: it was interrupted (restart) or cancelled
    const lastStopped = !!latestBuild && !building && !lastFailed && !lastReady;

    return (
        <div className="p-4 lg:p-6 space-y-4 max-w-3xl mx-auto">
            <div className="flex items-center gap-3 flex-wrap">
                <span className="text-sm font-bold text-slate-700 dark:text-slate-200 flex-1">
                    Пакеты ({packages.length})
                </span>
                {hasPending && (
                    <span className="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400">
                        <Loader2 size={12} className="animate-spin" /> Обновление...
                    </span>
                )}
                <button
                    onClick={handleBuild}
                    disabled={starting || building}
                    title={sessionId ? 'Полная сборка с проверкой; при ошибке ИИ чинит файлы (до 3 попыток)' : undefined}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold
                               bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50
                               shadow-lg shadow-blue-500/20"
                >
                    {starting || building ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
                    {sessionId ? 'Собрать (с ИИ-починкой)' : 'Собрать пакет'}
                </button>
            </div>

            {(building || latestBuild) && (
                <div className={`flex items-start gap-2 p-3 rounded-xl text-sm border
                    ${building ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-400'
                        : lastFailed ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-600 dark:text-red-400'
                            : lastStopped ? 'bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300'
                                : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-700 dark:text-green-400'}`}>
                    {building ? <Loader2 size={16} className="animate-spin shrink-0 mt-0.5" />
                        : lastFailed ? <Wrench size={16} className="shrink-0 mt-0.5" />
                            : lastStopped ? <AlertCircle size={16} className="shrink-0 mt-0.5" />
                                : <CheckCircle size={16} className="shrink-0 mt-0.5" />}
                    <div className="min-w-0">
                        <p className="font-bold">
                            {building ? 'Сборка и авто-починка…'
                                : lastFailed ? 'Последняя сборка не удалась'
                                    : lastStopped
                                        ? (latestBuild?.state === 'CANCELLED' ? 'Сборка отменена' : 'Сборка прервана — запустите её снова')
                                        : `Пакет #${latestBuild?.package_id} собран`}
                        </p>
                        {building && activeRun?.step && <p className="text-xs opacity-80 mt-0.5 break-words">{activeRun.step}</p>}
                        {!building && lastFailed && latestBuild?.comment && (
                            <p className="text-xs opacity-80 mt-0.5 break-words font-mono whitespace-pre-wrap">
                                {latestBuild.comment.slice(0, 1500)}
                            </p>
                        )}
                    </div>
                </div>
            )}

            {builds.length > 1 && (
                <details className="text-xs">
                    <summary className="cursor-pointer flex items-center gap-1.5 font-bold text-slate-500">
                        <History size={12} /> История сборок ИИ
                    </summary>
                    <ul className="mt-2 space-y-1">
                        {builds.map(b => (
                            <li key={b.id} className="flex gap-2 text-[11px] text-slate-600 dark:text-slate-300">
                                <span className="font-mono text-slate-400">попытка {b.attempt}</span>
                                <span>{b.package_id ? `#${b.package_id}` : '—'}</span>
                                <span className={b.state === 'READY' ? 'text-green-600'
                                    : isBuildFinal(b.state) ? 'text-red-500' : ''}>
                                    {b.state}
                                </span>
                                {b.comment && <span className="truncate text-slate-400" title={b.comment}>{b.comment}</span>}
                            </li>
                        ))}
                    </ul>
                </details>
            )}

            {error && (
                <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-xl text-sm">
                    <AlertCircle size={16} /> {error}
                </div>
            )}

            {packages.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                    <Package size={48} className="mb-3 opacity-10" />
                    <p className="font-bold">Нет пакетов</p>
                    <p className="text-xs mt-1">Нажмите «Собрать» для создания</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {packages.map(pkg => {
                        const conf = STATE_CONFIG[pkg.state] || STATE_CONFIG.PENDING;
                        return (
                            <div key={pkg.id} className="border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 bg-white dark:bg-slate-900">
                                <div className="flex items-center gap-3 flex-wrap">
                                    <span className="text-xs font-mono text-slate-500 shrink-0">#{pkg.id}</span>
                                    <span className="text-sm font-bold text-slate-700 dark:text-slate-200 flex-1 min-w-0 truncate">
                                        rev. {pkg.revision} &mdash; {pkg.type}
                                    </span>
                                    <span className={`flex items-center gap-1.5 text-[11px] font-bold px-2 py-0.5 rounded-full shrink-0 ${conf.color} ${conf.bg}`}>
                                        {conf.icon} {conf.label}
                                    </span>
                                    {pkg.state === 'READY' && (
                                        <div className="flex items-center gap-1 shrink-0">
                                            {DOWNLOAD_TYPES.map(t => (
                                                <button
                                                    key={t}
                                                    onClick={() => download(pkg, t)}
                                                    disabled={!!downloading}
                                                    title={`Скачать пакет (${t})`}
                                                    className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-lg
                                                               bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-blue-600 disabled:opacity-50"
                                                >
                                                    {downloading === `${pkg.id}-${t}`
                                                        ? <Loader2 size={10} className="animate-spin" /> : <Download size={10} />}
                                                    {t}
                                                </button>
                                            ))}
                                            <button
                                                onClick={() => setExportPackage(pkg.id)}
                                                title="Загрузить задачу в контест ejudge"
                                                className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-lg
                                                           bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 hover:bg-blue-100"
                                            >
                                                <Upload size={10} /> ejudge
                                            </button>
                                        </div>
                                    )}
                                </div>
                                <div className="mt-1.5">
                                    <span className="text-[11px] text-slate-400">{formatTime(pkg.creationTimeSeconds)}</span>
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

            {exportPackage !== null && (
                <EjudgeExportModal polygonId={polygonId} packageId={exportPackage} onClose={() => setExportPackage(null)} />
            )}
        </div>
    );
};
