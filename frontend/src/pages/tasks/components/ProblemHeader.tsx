// pages/tasks/components/ProblemHeader.tsx

import { ArrowLeft, ExternalLink, ChevronDown } from 'lucide-react';

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
}

export const ProblemHeader = ({ polygonId, name, problemType, onProblemTypeChange, savingType, onBack }: Props) => {
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

            {/* Problem type selector */}
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
