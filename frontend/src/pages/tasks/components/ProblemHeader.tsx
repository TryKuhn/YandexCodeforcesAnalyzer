// pages/tasks/components/ProblemHeader.tsx

import { ArrowLeft, ExternalLink, ChevronDown, RefreshCw, Loader2, CheckCircle, XCircle, Package } from 'lucide-react';
import { parseServerDate } from '../../../utils/date';
import { isActive, type AiBuild, type AiRun } from '../../../api/ai';

const PROBLEM_TYPES = [
    { id: 'regular',     label: 'Обычная' },
    { id: 'interactive', label: 'Интерактивная' },
    { id: 'output_only', label: 'Output-only' },
];

interface Props {
    polygonId: number;
    name: string;
    problemType: string;
    onProblemTypeChange: (t: string) => void;
    savingType?: boolean;
    onBack: () => void;
    latestBuild?: AiBuild | null;
    activeRun?: AiRun | null;
    lastSyncedAt?: string | null;
    syncError?: string | null;
    syncing?: boolean;
    onSync?: () => void;
    onOpenPackages?: () => void;
}

const sinceText = (ts: string | null | undefined) => {
    if (!ts) return 'не синхронизировано';
    const minutes = Math.floor((Date.now() - parseServerDate(ts).getTime()) / 60000);
    if (minutes < 1) return 'синхр. только что';
    if (minutes < 60) return `синхр. ${minutes} мин назад`;
    return `синхр. ${parseServerDate(ts).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`;
};

const BuildBadge = ({ build, run, onClick }: { build?: AiBuild | null; run?: AiRun | null; onClick?: () => void }) => {
    const building = run && isActive(run) && run.kind === 'build';
    if (!build && !building) return null;
    let cls = 'bg-slate-100 dark:bg-slate-800 text-slate-500';
    let icon = <Package size={11} />;
    let label = 'Пакет';
    if (building) {
        cls = 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400';
        icon = <Loader2 size={11} className="animate-spin" />;
        label = run?.step || 'Сборка…';
    } else if (build?.state === 'READY') {
        cls = 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400';
        icon = <CheckCircle size={11} />;
        label = `Пакет #${build.package_id} собран`;
    } else if (build && ['FAILED', 'TIMEOUT', 'ERROR'].includes(build.state)) {
        cls = 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400';
        icon = <XCircle size={11} />;
        label = build.package_id ? `Пакет #${build.package_id}: ошибка` : 'Сборка: ошибка';
    } else if (build?.state === 'CANCELLED') {
        label = 'Сборка отменена';
    } else if (build && run && isActive(run)) {
        cls = 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400';
        icon = <Loader2 size={11} className="animate-spin" />;
        label = `Сборка: ${build.state}`;
    } else if (build) {
        // not final, and nothing runs any more: the service was restarted mid-build
        label = 'Сборка прервана';
    }
    return (
        <button
            onClick={onClick}
            title={build?.comment || undefined}
            className={`hidden md:flex items-center gap-1.5 text-[10px] font-bold px-2.5 py-1 rounded-full max-w-[260px] ${cls}`}
        >
            {icon}
            <span className="truncate">{label}</span>
        </button>
    );
};

export const ProblemHeader = ({
    polygonId, name, problemType, onProblemTypeChange, savingType, onBack,
    latestBuild, activeRun, lastSyncedAt, syncError, syncing, onSync, onOpenPackages,
}: Props) => {
    return (
        <div className="h-14 shrink-0 flex items-center gap-3 px-4 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
            <button
                onClick={onBack}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold
                           text-slate-500 hover:text-slate-900 dark:hover:text-white
                           hover:bg-slate-100 dark:hover:bg-slate-800 transition-all shrink-0"
            >
                <ArrowLeft size={14} />
                <span className="hidden sm:inline">Задачи</span>
            </button>

            <div className="w-px h-5 bg-slate-200 dark:bg-slate-700 shrink-0" />

            <span className="font-bold text-slate-800 dark:text-white text-sm truncate max-w-[200px] sm:max-w-xs">
                {name || `Задача #${polygonId}`}
            </span>

            <div className="relative shrink-0">
                <select
                    value={problemType}
                    onChange={e => onProblemTypeChange(e.target.value)}
                    disabled={savingType}
                    className="appearance-none text-[10px] font-bold rounded-full pl-2.5 pr-6 py-1 outline-none cursor-pointer
                               border transition-all disabled:opacity-50
                               bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200
                               border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700"
                >
                    {PROBLEM_TYPES.map(t => (
                        <option key={t.id} value={t.id} className="bg-white dark:bg-slate-800 text-slate-900 dark:text-white">
                            {t.label}
                        </option>
                    ))}
                </select>
                <ChevronDown size={10} className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400" />
            </div>

            <BuildBadge build={latestBuild} run={activeRun} onClick={onOpenPackages} />

            <div className="flex-1" />

            {onSync && (
                <button
                    onClick={onSync}
                    disabled={syncing}
                    title={syncError || 'Перечитать задачу из Polygon'}
                    className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-[10px] font-bold transition-all
                        ${syncError ? 'text-amber-600 dark:text-amber-400' : 'text-slate-400 hover:text-blue-600 dark:hover:text-blue-400'}
                        hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50`}
                >
                    <RefreshCw size={12} className={syncing ? 'animate-spin' : ''} />
                    {syncing ? 'синхронизация…' : sinceText(lastSyncedAt)}
                </button>
            )}

            <a
                href={`https://polygon.codeforces.com/problems/${polygonId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold
                           text-slate-500 hover:text-blue-600 dark:hover:text-blue-400
                           hover:bg-slate-100 dark:hover:bg-slate-800 transition-all shrink-0"
            >
                <span className="hidden sm:inline">Polygon</span>
                <ExternalLink size={13} />
            </a>
        </div>
    );
};
