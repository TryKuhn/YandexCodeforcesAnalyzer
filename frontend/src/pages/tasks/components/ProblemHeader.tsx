// pages/tasks/components/ProblemHeader.tsx

import { ArrowLeft, ExternalLink, Zap } from 'lucide-react';

interface Props {
    polygonId: number;
    name: string;
    interactive: boolean;
    onBack: () => void;
}

export const ProblemHeader = ({ polygonId, name, interactive, onBack }: Props) => {
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

            {interactive && (
                <span className="flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded-full
                                 bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 shrink-0">
                    <Zap size={10} />
                    интерактивная
                </span>
            )}

            <div className="flex-1" />

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
