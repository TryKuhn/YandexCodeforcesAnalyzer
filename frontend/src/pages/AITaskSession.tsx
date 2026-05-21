// pages/AITaskSession.tsx

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Send, Sparkles, Loader2, CheckCircle, AlertCircle,
    FileText, UploadCloud, Code, BookOpen,
    Terminal, RefreshCw, Edit3, Check, X, Package,
    AlertTriangle, ChevronRight, ArrowLeft, Plus, Settings,
    ChevronDown, ChevronUp, Trash2, FlaskConical, ExternalLink
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/cjs/styles/prism';
import { api } from '../api/instance';
import { useAISettings, AI_MODELS } from '../components/layout/MainLayout';

// ─────────────────────────── Константы ──────────────────────────────────────

const STATIC_FILE_LABELS: Record<string, string> = {
    validator:    'validator.cpp',
    generator:    'generator.cpp',
    checker:      'checker.cpp',
    interactor:   'interactor.cpp',
    solution_cpp: 'solution.cpp',
    solution_py:  'solution_py.py',
    wa_sol:       'wa.cpp',
    tl_sol:       'tl.cpp',
    re_sol:       're.cpp',
    ml_sol:       'ml.cpp',
    script:       'script.txt',
};

const FILE_LANGUAGES: Record<string, string> = {
    validator:    'cpp',
    generator:    'cpp',
    checker:      'cpp',
    interactor:   'cpp',
    solution_cpp: 'cpp',
    solution_py:  'python',
    wa_sol:       'cpp',
    tl_sol:       'cpp',
    re_sol:       'cpp',
    ml_sol:       'cpp',
    script:       'ftl',
};

const SOLUTION_TAGS = ['MA', 'OK', 'WA', 'TL', 'ML', 'RE', 'RJ'];

// ─────────────────────────── Типы ───────────────────────────────────────────

type PipelineStage =
    | 'statement'
    | 'files_review'
    | 'uploading'
    | 'fixing_errors'
    | 'building_package'
    | 'done'
    | 'failed';

interface Statement {
    name: string;
    legend: string;
    input: string;
    output: string;
    notes?: string;
    tutorial?: string;
    interaction?: string;
    scoring?: string;
}

interface TechnicalData {
    [key: string]: string;
}

interface SolutionMeta {
    [fileType: string]: { tag: string; name: string };
}

interface ProblemSettings {
    input_file: string;
    output_file: string;
    interactive: boolean;
    time_limit: number;
    memory_limit: number;
    tags: string[];
    enable_groups: boolean;
    enable_points: boolean;
}

interface ExampleTest {
    index: number;
    input: string;
    output: string;
}

interface UploadError {
    file_name: string;
    error: string;
    needs_manual_fix: boolean;
}

interface Progress {
    status: string;
    current_step?: string;
    error?: string;
    retries?: number;
}


const EDITABLE_STAGES: PipelineStage[] = ['files_review', 'fixing_errors', 'failed', 'done'];
const canEditFiles = (stage: PipelineStage) => EDITABLE_STAGES.includes(stage);


const StepBadge = ({ stage }: { stage: PipelineStage }) => {
    const steps: { key: PipelineStage; label: string }[] = [
        { key: 'statement',        label: 'Условие' },
        { key: 'files_review',     label: 'Файлы' },
        { key: 'uploading',        label: 'Загрузка' },
        { key: 'building_package', label: 'Пакет' },
        { key: 'done',             label: 'Готово' },
    ];

    const stageOrder: Record<string, number> = {
        statement: 0, files_review: 1, uploading: 2,
        fixing_errors: 2, building_package: 3, done: 4, failed: -1,
    };

    const currentIdx = stageOrder[stage] ?? 0;

    return (
        <div className="flex items-center gap-1">
            {steps.map((s, i) => {
                const idx = stageOrder[s.key];
                const done = idx < currentIdx;
                const active = idx === currentIdx;
                return (
                    <div key={s.key} className="flex items-center gap-1">
                        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold transition-all
                            ${done   ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : ''}
                            ${active ? 'bg-blue-100  text-blue-700  dark:bg-blue-900/30  dark:text-blue-400'  : ''}
                            ${!done && !active ? 'bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-600' : ''}
                        `}>
                            {done && <Check size={10} />}
                            {s.label}
                        </div>
                        {i < steps.length - 1 && <ChevronRight size={10} className="text-slate-300 dark:text-slate-700" />}
                    </div>
                );
            })}
        </div>
    );
};


const ProblemSettingsPanel = ({
    settings, onChange, onSuggestTags, onGenerateSamples, sessionId, suggestingTags, generatingSamples
}: {
    settings: ProblemSettings;
    onChange: (s: ProblemSettings) => void;
    onSuggestTags: () => void;
    onGenerateSamples: () => void;
    sessionId: string | null;
    suggestingTags: boolean;
    generatingSamples: boolean;
}) => {
    const [open, setOpen] = useState(false);
    const [tagInput, setTagInput] = useState('');

    const addTag = (tag: string) => {
        const t = tag.trim().toLowerCase();
        if (t && !settings.tags.includes(t)) {
            onChange({ ...settings, tags: [...settings.tags, t] });
        }
        setTagInput('');
    };

    return (
        <div className="border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
            <button
                onClick={() => setOpen(o => !o)}
                className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-50 dark:bg-slate-800/50 text-xs font-bold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
            >
                <div className="flex items-center gap-2">
                    <Settings size={14} />
                    Настройки задачи
                </div>
                {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            {open && (
                <div className="p-4 bg-white dark:bg-slate-900 space-y-3">
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 mb-1">Input файл</label>
                            <input
                                value={settings.input_file}
                                onChange={e => onChange({ ...settings, input_file: e.target.value })}
                                className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                                placeholder="stdin"
                            />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 mb-1">Output файл</label>
                            <input
                                value={settings.output_file}
                                onChange={e => onChange({ ...settings, output_file: e.target.value })}
                                className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                                placeholder="stdout"
                            />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 mb-1">Time Limit (мс)</label>
                            <input
                                type="number"
                                value={settings.time_limit}
                                onChange={e => onChange({ ...settings, time_limit: Number(e.target.value) })}
                                className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                            />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 mb-1">Memory Limit (МБ)</label>
                            <input
                                type="number"
                                value={settings.memory_limit}
                                onChange={e => onChange({ ...settings, memory_limit: Number(e.target.value) })}
                                className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                            />
                        </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={settings.interactive}
                                onChange={e => onChange({ ...settings, interactive: e.target.checked })}
                                className="rounded"
                            />
                            <span className="text-xs font-bold text-slate-600 dark:text-slate-300">Интерактивная</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={settings.enable_groups}
                                onChange={e => onChange({ ...settings, enable_groups: e.target.checked })}
                                className="rounded"
                            />
                            <span className="text-xs font-bold text-slate-600 dark:text-slate-300">Группы тестов</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={settings.enable_points}
                                onChange={e => onChange({ ...settings, enable_points: e.target.checked })}
                                className="rounded"
                            />
                            <span className="text-xs font-bold text-slate-600 dark:text-slate-300">Баллы</span>
                        </label>
                    </div>

                    <div>
                        <div className="flex items-center justify-between mb-1.5">
                            <label className="text-[10px] font-bold text-slate-500">Теги</label>
                            <button
                                onClick={onSuggestTags}
                                disabled={suggestingTags || !sessionId}
                                className="flex items-center gap-1 text-[10px] font-bold text-blue-500 hover:text-blue-700 disabled:opacity-50 transition-colors"
                            >
                                {suggestingTags ? <Loader2 size={10} className="animate-spin" /> : <Sparkles size={10} />}
                                Предложить ИИ
                            </button>
                        </div>
                        <div className="flex flex-wrap gap-1 mb-2">
                            {settings.tags.map(tag => (
                                <span
                                    key={tag}
                                    className="flex items-center gap-1 px-2 py-0.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full text-[10px] font-bold"
                                >
                                    {tag}
                                    <button onClick={() => onChange({ ...settings, tags: settings.tags.filter(t => t !== tag) })}>
                                        <X size={8} />
                                    </button>
                                </span>
                            ))}
                        </div>
                        <div className="flex gap-1">
                            <input
                                value={tagInput}
                                onChange={e => setTagInput(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter') { addTag(tagInput); e.preventDefault(); } }}
                                placeholder="Добавить тег..."
                                className="flex-1 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                            />
                            <button
                                onClick={() => addTag(tagInput)}
                                className="px-2 py-1.5 bg-slate-100 dark:bg-slate-800 rounded-lg text-xs hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
                            >
                                <Plus size={12} />
                            </button>
                        </div>
                    </div>

                    <button
                        onClick={onGenerateSamples}
                        disabled={generatingSamples || !sessionId}
                        className="flex items-center gap-2 w-full justify-center text-xs font-bold py-2 bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 hover:bg-purple-100 dark:hover:bg-purple-900/40 rounded-xl transition-all disabled:opacity-50"
                    >
                        {generatingSamples ? <Loader2 size={14} className="animate-spin" /> : <FlaskConical size={14} />}
                        Сгенерировать примеры (ИИ)
                    </button>

                </div>
            )}
        </div>
    );
};


const AddSolutionModal = ({ onClose, onAdd }: {
    onClose: () => void;
    onAdd: (tag: string, name: string) => void;
}) => {
    const [tag, setTag] = useState('WA');
    const [name, setName] = useState('');

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-6 w-80 border border-slate-200 dark:border-slate-700">
                <h3 className="font-black text-sm text-slate-800 dark:text-white mb-4 flex items-center gap-2">
                    <Plus size={16} className="text-blue-500" />
                    Добавить решение
                </h3>
                <div className="space-y-3">
                    <div>
                        <label className="text-[10px] font-bold text-slate-500 block mb-1">Тег решения</label>
                        <select
                            value={tag}
                            onChange={e => setTag(e.target.value)}
                            className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-2 outline-none dark:text-white"
                        >
                            {SOLUTION_TAGS.map(t => (
                                <option key={t} value={t}>{t}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="text-[10px] font-bold text-slate-500 block mb-1">Название файла</label>
                        <input
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder="brute_force (без .cpp)"
                            className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-2 outline-none dark:text-white"
                        />
                    </div>
                </div>
                <div className="flex gap-2 mt-5">
                    <button
                        onClick={() => { if (name.trim()) onAdd(tag, name.trim()); }}
                        disabled={!name.trim()}
                        className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-xs font-black py-2 rounded-xl disabled:opacity-50 transition-all"
                    >
                        Создать
                    </button>
                    <button
                        onClick={onClose}
                        className="flex-1 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-xs font-bold py-2 rounded-xl hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
                    >
                        Отмена
                    </button>
                </div>
            </div>
        </div>
    );
};


const LaTeXTableCell = ({ content }: { content: string }) => {
    if (!content.includes('$')) return <>{content}</>;
    return (
        <ReactMarkdown
            remarkPlugins={[remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={{ p: ({ children }) => <>{children}</> }}
        >
            {content}
        </ReactMarkdown>
    );
};

const LaTeXTable = ({ latex }: { latex: string }) => {
    const tabMatch = latex.match(/\\begin\{tabular\}([\s\S]*?)\\end\{tabular\}/);
    if (!tabMatch) {
        return (
            <pre className="text-xs font-mono bg-slate-50 dark:bg-slate-800 p-3 rounded-xl overflow-x-auto border border-slate-200 dark:border-slate-700 mt-2 whitespace-pre-wrap">
                {latex}
            </pre>
        );
    }

    const inner = tabMatch[1]
        .replace(/^\s*\{[^}]*\}\s*/, '')  // remove column spec { | c | c | ... }
        .trim();

    const cleanCell = (cell: string): string =>
        cell
            .replace(/\\textbf\s*\{\\scriptsize\s*\{([^}]*)\}\}/g, '$1')
            .replace(/\\textbf\s*\{([^}]*)\}/g, '$1')
            .replace(/\\scriptsize\s*\{([^}]*)\}/g, '$1')
            .replace(/\\hline/g, '')
            .replace(/\s+/g, ' ')
            .trim();

    const rows = inner
        .split('\\\\')
        .map(seg => seg.replace(/\\hline/g, '').trim())
        .filter(seg => seg.length > 0)
        .map(seg => seg.split('&').map(cleanCell));

    if (rows.length === 0) return null;
    const [header, ...body] = rows;

    return (
        <div className="overflow-x-auto mt-3">
            <table className="border-collapse text-sm w-full">
                <thead>
                    <tr>
                        {header.map((cell, i) => (
                            <th key={i} className="border border-slate-300 dark:border-slate-600 px-3 py-2 text-center text-xs font-bold bg-slate-100 dark:bg-slate-800 whitespace-nowrap">
                                <LaTeXTableCell content={cell} />
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {body.map((row, i) => (
                        <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                            {row.map((cell, j) => (
                                <td key={j} className="border border-slate-300 dark:border-slate-600 px-3 py-2 text-center text-xs">
                                    <LaTeXTableCell content={cell} />
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};


type LatexBlock =
    | { t: 'text';         src: string }
    | { t: 'display-math'; src: string }
    | { t: 'verbatim';     src: string }
    | { t: 'center';       src: string }
    | { t: 'itemize';      items: string[] }
    | { t: 'enumerate';    items: string[] };

const splitLatexBlocks = (text: string): LatexBlock[] => {
    const blocks: LatexBlock[] = [];
    const re = /\$\$([\s\S]*?)\$\$|\\begin\{(verbatim|itemize|enumerate|center)\}([\s\S]*?)\\end\{\2\}/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
        if (m.index > last) blocks.push({ t: 'text', src: text.slice(last, m.index) });
        if (m[1] !== undefined) {
            blocks.push({ t: 'display-math', src: m[1] });
        } else {
            const env = m[2] as 'verbatim' | 'itemize' | 'enumerate' | 'center';
            const content = m[3].trim();
            if (env === 'itemize' || env === 'enumerate') {
                blocks.push({ t: env, items: content.split('\\item').slice(1).map((s: string) => s.trim()) });
            } else if (env === 'verbatim') {
                blocks.push({ t: 'verbatim', src: content });
            } else {
                blocks.push({ t: 'center', src: content });
            }
        }
        last = m.index + m[0].length;
    }
    if (last < text.length) blocks.push({ t: 'text', src: text.slice(last) });
    return blocks;
};

const inlineLatexToMd = (text: string): string => {
    if (!text) return text;
    const saved: string[] = [];
    const save = (s: string) => { saved.push(s); return `\x00${saved.length - 1}\x00`; };
    let t = text;
    t = t.replace(/\\\$/g, save(''));
    t = t.replace(/\$([^$\n]+?)\$/g, m => save(m));
    const replaceCmd = (cmd: string, open: string, close: string) => {
        const re = new RegExp(`\\\\${cmd}\\{`, 'g');
        let out = '', last = 0, mc: RegExpExecArray | null;
        while ((mc = re.exec(t)) !== null) {
            out += t.slice(last, mc.index);
            let depth = 1, i = mc.index + mc[0].length;
            while (i < t.length && depth > 0) {
                if (t[i] === '{') depth++;
                else if (t[i] === '}') depth--;
                i++;
            }
            out += open + t.slice(mc.index + mc[0].length, i - 1) + close;
            last = i;
            re.lastIndex = i;
        }
        t = out + t.slice(last);
    };
    replaceCmd('textbf', '**', '**');
    replaceCmd('textit', '*', '*');
    replaceCmd('emph', '*', '*');
    replaceCmd('texttt', '`', '`');
    replaceCmd('underline', '', '');
    replaceCmd('text', '', '');
    replaceCmd('textsc', '', '');
    t = t.replace(/\\ldots\b/g, '...').replace(/\\dots\b/g, '...');
    t = t.replace(/\x00(\d+)\x00/g, (_, i) => saved[+i]);
    t = t.replace(//g, "$");
    return t;
};

const MdInline = ({ children }: { children: string }) => (
    <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{ p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p> }}
    >
        {inlineLatexToMd(children || '')}
    </ReactMarkdown>
);

const LatexRenderer = ({ children }: { children: string | undefined }) => {
    const blocks = splitLatexBlocks(children || '');
    return (
        <>
            {blocks.map((block, i) => {
                if (block.t === 'display-math') return (
                    <div key={i} className="overflow-x-auto py-1 text-center">
                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                            {`$$${block.src}$$`}
                        </ReactMarkdown>
                    </div>
                );
                if (block.t === 'verbatim') return (
                    <pre key={i} className="text-xs font-mono bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3 overflow-x-auto my-2 whitespace-pre-wrap">
                        {block.src}
                    </pre>
                );
                if (block.t === 'itemize') return (
                    <ul key={i} className="list-disc list-inside space-y-0.5 my-1">
                        {block.items.map((item, j) => <li key={j}><MdInline>{item}</MdInline></li>)}
                    </ul>
                );
                if (block.t === 'enumerate') return (
                    <ol key={i} className="list-decimal list-inside space-y-0.5 my-1">
                        {block.items.map((item, j) => <li key={j}><MdInline>{item}</MdInline></li>)}
                    </ol>
                );
                if (block.t === 'center') return (
                    block.src.includes('\\begin{tabular}')
                        ? <LaTeXTable key={i} latex={block.src} />
                        : <div key={i} className="text-center my-2"><MdInline>{block.src}</MdInline></div>
                );
                return <MdInline key={i}>{block.src}</MdInline>;
            })}
        </>
    );
};


const EditableScoringTable = ({ latex, onSave, onCancel }: {
    latex: string;
    onSave: (newLatex: string) => void;
    onCancel: () => void;
}) => {
    const parseRows = (src: string): string[][] => {
        const tabMatch = src.match(/\\begin\{tabular\}([\s\S]*?)\\end\{tabular\}/);
        if (!tabMatch) return [['']];
        const inner = tabMatch[1].replace(/^\s*\{[^}]*\}\s*/, '').trim();
        const cleanCell = (c: string) =>
            c.replace(/\\textbf\s*\{\\scriptsize\s*\{([^}]*)\}\}/g, '$1')
             .replace(/\\textbf\s*\{([^}]*)\}/g, '$1')
             .replace(/\\scriptsize\s*\{([^}]*)\}/g, '$1')
             .replace(/\\hline/g, '')
             .replace(/\s+/g, ' ')
             .trim();
        return inner
            .split('\\\\')
            .map(s => s.replace(/\\hline/g, '').trim())
            .filter(s => s.length > 0)
            .map(s => s.split('&').map(cleanCell));
    };

    const [rows, setRows] = useState<string[][]>(() => parseRows(latex));
    const cols = rows[0]?.length || 1;

    const updateCell = (ri: number, ci: number, val: string) =>
        setRows(prev => prev.map((row, i) =>
            i === ri ? row.map((cell, j) => j === ci ? val : cell) : row
        ));

    const addRow = () => setRows(prev => [...prev, Array(cols).fill('')]);

    const removeRow = (ri: number) => {
        if (rows.length <= 2) return;
        setRows(prev => prev.filter((_, i) => i !== ri));
    };

    const serialize = (): string => {
        if (rows.length === 0) return latex;
        const [header, ...data] = rows;
        const n = header.length;
        const spec = '| ' + Array(n).fill('c').join(' | ') + ' |';
        const headerStr = header.map(h => `\\textbf{\\scriptsize{${h}}}`).join(' & ');
        const lines = [
            `        ${headerStr} \\\\ \\hline`,
            ...data.map(r => `        ${r.map(c => c || '--').join(' & ')} \\\\ \\hline`),
        ];
        return `\\begin{center}\n    \\begin{tabular}{ ${spec} }\n        \\hline\n${lines.join('\n')}\n    \\end{tabular}\n\\end{center}`;
    };

    return (
        <div className="mt-2 space-y-3">
            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
                <table className="border-collapse w-full text-sm">
                    <thead>
                        <tr>
                            {rows[0]?.map((cell, j) => (
                                <th key={j} className="border border-slate-300 dark:border-slate-600 bg-slate-100 dark:bg-slate-800 px-2 py-1.5 min-w-[90px]">
                                    <input
                                        value={cell}
                                        onChange={e => updateCell(0, j, e.target.value)}
                                        className="w-full text-xs font-bold text-center bg-transparent outline-none dark:text-white"
                                    />
                                </th>
                            ))}
                            <th className="w-7 bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-600" />
                        </tr>
                    </thead>
                    <tbody>
                        {rows.slice(1).map((row, i) => (
                            <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                                {row.map((cell, j) => (
                                    <td key={j} className="border border-slate-300 dark:border-slate-600 px-2 py-1">
                                        <input
                                            value={cell}
                                            onChange={e => updateCell(i + 1, j, e.target.value)}
                                            className="w-full text-xs text-center bg-transparent outline-none dark:text-white min-w-[70px]"
                                        />
                                    </td>
                                ))}
                                <td className="border border-slate-300 dark:border-slate-600 px-1 text-center">
                                    <button
                                        onClick={() => removeRow(i + 1)}
                                        disabled={rows.length <= 2}
                                        className="text-slate-300 hover:text-red-400 disabled:opacity-20 transition-colors"
                                    >
                                        <X size={12} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <button
                onClick={addRow}
                className="flex items-center gap-1 text-xs text-slate-400 hover:text-blue-500 transition-colors"
            >
                <Plus size={12} /> Добавить строку
            </button>
            <div className="flex gap-2">
                <button onClick={() => onSave(serialize())} className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-all">
                    <Check size={12} /> Сохранить
                </button>
                <button onClick={onCancel} className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 px-3 py-1.5 rounded-lg transition-all">
                    <X size={12} /> Отмена
                </button>
            </div>
        </div>
    );
};


const ExamplesPanel = ({ examples, onUpdate }: {
    examples: ExampleTest[];
    onUpdate: (examples: ExampleTest[]) => void;
}) => {
    const [editingIdx, setEditingIdx] = useState<number | null>(null);

    if (examples.length === 0) return null;

    return (
        <div className="mt-8">
            <h3 className="text-xl font-bold mb-4 border-b pb-2 flex items-center gap-2">
                <FlaskConical size={18} className="text-purple-500" />
                Примеры
            </h3>
            <div className="space-y-4">
                {examples.map((ex, i) => (
                    <div key={i} className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
                        <div className="flex items-center justify-between px-3 py-1.5 bg-slate-50 dark:bg-slate-800/50 text-xs font-bold text-slate-500">
                            <span>Пример {ex.index || i + 1}</span>
                            <div className="flex gap-2">
                                <button onClick={() => setEditingIdx(editingIdx === i ? null : i)} className="hover:text-blue-500 transition-colors">
                                    <Edit3 size={12} />
                                </button>
                                <button onClick={() => onUpdate(examples.filter((_, j) => j !== i))} className="hover:text-red-500 transition-colors">
                                    <Trash2 size={12} />
                                </button>
                            </div>
                        </div>
                        {editingIdx === i ? (
                            <div className="p-3 space-y-2">
                                <div>
                                    <label className="text-[10px] font-bold text-slate-500 mb-1 block">Входные данные</label>
                                    <textarea
                                        value={ex.input}
                                        onChange={e => onUpdate(examples.map((x, j) => j === i ? { ...x, input: e.target.value } : x))}
                                        className="w-full font-mono text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2 outline-none dark:text-white resize-none"
                                        rows={3}
                                    />
                                </div>
                                <div>
                                    <label className="text-[10px] font-bold text-slate-500 mb-1 block">Выходные данные</label>
                                    <textarea
                                        value={ex.output}
                                        onChange={e => onUpdate(examples.map((x, j) => j === i ? { ...x, output: e.target.value } : x))}
                                        className="w-full font-mono text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2 outline-none dark:text-white resize-none"
                                        rows={3}
                                    />
                                </div>
                                <button
                                    onClick={() => setEditingIdx(null)}
                                    className="text-xs text-blue-500 font-bold hover:text-blue-700"
                                >
                                    Готово
                                </button>
                            </div>
                        ) : (
                            <div className="grid grid-cols-2 divide-x divide-slate-200 dark:divide-slate-700">
                                <div className="p-3">
                                    <div className="text-[10px] font-bold text-slate-400 mb-1">Вход</div>
                                    <pre className="font-mono text-xs text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{ex.input || '—'}</pre>
                                </div>
                                <div className="p-3">
                                    <div className="text-[10px] font-bold text-slate-400 mb-1">Выход</div>
                                    <pre className="font-mono text-xs text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{ex.output || '—'}</pre>
                                </div>
                            </div>
                        )}
                    </div>
                ))}
                <button
                    onClick={() => onUpdate([...examples, { index: examples.length + 1, input: '', output: '' }])}
                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                >
                    <Plus size={12} /> Добавить пример
                </button>
            </div>
        </div>
    );
};

interface ChatLogEntry {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: string;
    context?: string;
    action?: string;
    updated_files?: string[];
}

const DEFAULT_SETTINGS: ProblemSettings = {
    input_file: 'stdin', output_file: 'stdout', interactive: false,
    time_limit: 2000, memory_limit: 256, tags: [], enable_groups: false, enable_points: false,
};

export const AITaskSession = () => {
    const { sessionId: urlSessionId } = useParams<{ sessionId: string }>();
    const navigate = useNavigate();
    const { load: loadSettings, save: saveSettings } = useAISettings();

    const [sessionModel, setSessionModel] = useState<string>(() => loadSettings().model);
    const [chatLog, setChatLog]        = useState<ChatLogEntry[]>([]);
    const [inputValue, setInputValue] = useState('');
    const [loading, setLoading]       = useState(false);

    const [sessionId, setSessionId]               = useState<string | null>(urlSessionId || null);
    const [stage, setStage]                       = useState<PipelineStage>('statement');
    const [statement, setStatement]               = useState<Statement | null>(null);
    const [techData, setTechData]                 = useState<TechnicalData | null>(null);
    const [uploadErrors, setUploadErrors]         = useState<Record<string, UploadError> | null>(null);
    const [polygonProblemId, setPolygonProblemId] = useState<number | null>(null);
    const [progress, setProgress]                 = useState<Progress>({ status: 'idle' });
    const [initialLoading, setInitialLoading]     = useState(true);
    const [problemSettings, setProblemSettings]   = useState<ProblemSettings>(DEFAULT_SETTINGS);
    const [solutionMeta, setSolutionMeta]         = useState<SolutionMeta>({});
    const [examples, setExamples]                 = useState<ExampleTest[]>([]);

    const [viewMode, setViewMode]         = useState<'statement' | 'tutorial' | 'files'>('statement');
    const [selectedFile, setSelectedFile] = useState<string>('solution_cpp');
    const [editingFile, setEditingFile]   = useState<string | null>(null);
    const [editContent, setEditContent]   = useState('');
    const [chatContext, setChatContext] = useState<'statement' | 'task' | string>('task');

    const [showAddSolution, setShowAddSolution] = useState(false);
    const [suggestingTags, setSuggestingTags]   = useState(false);
    const [generatingSamples, setGeneratingSamples] = useState(false);
    const [settingsDirty, setSettingsDirty]     = useState(false);
    const [editingStatementField, setEditingStatementField] = useState<string | null>(null);
    const [statementFieldValue, setStatementFieldValue] = useState('');
    const [mobileTab, setMobileTab]             = useState<'content' | 'chat'>('content');

    const chatEndRef = useRef<HTMLDivElement>(null);
    const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const settingsDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatLog]);

    useEffect(() => {
        if (stage === 'statement') setChatContext('statement');
        else if (stage === 'files_review') setChatContext('task');
    }, [stage]);

    useEffect(() => {
        if (!urlSessionId) { setInitialLoading(false); return; }

        api.get(`/ai/session/${urlSessionId}`)
            .then(res => {
                const d = res.data;
                setSessionId(d.session_id);
                setStage(d.stage);
                setStatement(d.statement);
                setTechData(d.technical_data && Object.keys(d.technical_data).length ? d.technical_data : null);
                setSessionModel(d.model);
                setProgress(d.progress || { status: 'idle' });
                if (d.upload_errors && Object.keys(d.upload_errors).length)
                    setUploadErrors(d.upload_errors);
                if (d.polygon_problem_id)
                    setPolygonProblemId(d.polygon_problem_id);
                if (d.problem_settings && Object.keys(d.problem_settings).length)
                    setProblemSettings({ ...DEFAULT_SETTINGS, ...d.problem_settings });
                if (d.solution_meta)
                    setSolutionMeta(d.solution_meta);
                if (d.examples)
                    setExamples(d.examples);

                if (d.stage !== 'statement' && d.technical_data && Object.keys(d.technical_data).length)
                    setViewMode('files');

                if (d.stage === 'uploading' || d.stage === 'building_package')
                    startPolling(d.session_id);

                const persisted: ChatLogEntry[] = d.chat_log || [];
                setChatLog([
                    ...persisted,
                    { id: 'sys-load', role: 'system', content: `Сессия загружена. Этап: ${stageLabel(d.stage)}`, timestamp: new Date().toISOString() },
                ]);
            })
            .catch(() => {
                addSystemMessage('❌ Сессия не найдена');
                setTimeout(() => navigate('/ai-tasks'), 2000);
            })
            .finally(() => setInitialLoading(false));
    }, [urlSessionId]);

    useEffect(() => {
        if (!sessionId || !settingsDirty) return;
        if (settingsDebounceRef.current) clearTimeout(settingsDebounceRef.current);
        settingsDebounceRef.current = setTimeout(async () => {
            try {
                await api.patch(`/ai/session/${sessionId}/problem-settings`, { settings: problemSettings });
                setSettingsDirty(false);
            } catch { /* non-critical */ }
        }, 800);
    }, [problemSettings, sessionId, settingsDirty]);

    const handleSettingsChange = (s: ProblemSettings) => {
        setProblemSettings(s);
        setSettingsDirty(true);
        if ((s.enable_groups || s.enable_points) && !statement?.scoring) {
            const defaultScoring =
                '\\begin{center}\n    \\begin{tabular}{ | c | c | c | }\n        \\hline\n' +
                '        \\textbf{\\scriptsize{Группа}} & \\textbf{\\scriptsize{Баллы}} & \\textbf{\\scriptsize{Условия}} \\\\ \\hline\n' +
                '        1 & -- & -- \\\\ \\hline\n    \\end{tabular}\n\\end{center}';
            setStatement(prev => prev ? { ...prev, scoring: defaultScoring } : prev);
        }
    };

    const handleModelChange = async (newModel: string) => {
        setSessionModel(newModel);
        const settings = loadSettings();
        saveSettings({ ...settings, model: newModel });
        if (sessionId) {
            try {
                await api.patch(`/ai/session/${sessionId}/settings`, { model: newModel });
            } catch { /* non-critical */ }
        }
    };

    useEffect(() => () => { if (pollingRef.current) clearInterval(pollingRef.current); }, []);


    const stageLabel = (s: PipelineStage) => ({
        statement: 'Работа с условием', files_review: 'Проверка файлов',
        uploading: 'Загрузка в Polygon', fixing_errors: 'Исправление ошибок',
        building_package: 'Сборка пакета', done: 'Готово', failed: 'Ошибка',
    }[s] || s);

    const addSystemMessage = (content: string) =>
        setChatLog(prev => [...prev, {
            id: crypto.randomUUID(),
            role: 'system',
            content,
            timestamp: new Date().toISOString(),
        }]);

    const getFileLabel = (key: string) => {
        if (STATIC_FILE_LABELS[key]) return STATIC_FILE_LABELS[key];
        if (solutionMeta[key]) return solutionMeta[key].name;
        return key;
    };

    const getFileLang = (key: string) => {
        if (FILE_LANGUAGES[key]) return FILE_LANGUAGES[key];
        return 'cpp';
    };

    const handleBackToFiles = () => {
        setStage('files_review');
        setViewMode('files');
        setProgress({ status: 'idle' });
        addSystemMessage('📝 Вернулись к редактированию файлов. Исправьте и повторите загрузку.');
    };


    const startPolling = useCallback((sid: string) => {
        if (pollingRef.current) clearInterval(pollingRef.current);

        pollingRef.current = setInterval(async () => {
            try {
                const res = await api.get(`/ai/upload-progress/${sid}`);
                const d = res.data;

                setProgress({ status: d.status, current_step: d.current_step, error: d.error, retries: d.retries });

                if (d.stage) setStage(d.stage);
                if (d.technical_data) setTechData(d.technical_data);
                if (d.upload_errors && Object.keys(d.upload_errors).length)
                    setUploadErrors(d.upload_errors);
                if (d.polygon_problem_id)
                    setPolygonProblemId(d.polygon_problem_id);

                if (d.status === 'done') {
                    clearInterval(pollingRef.current!);
                    addSystemMessage(`✅ Задача создана! ID: ${d.polygon_problem_id}`);
                }
                if (d.status === 'failed') {
                    clearInterval(pollingRef.current!);
                    addSystemMessage(`❌ Ошибка: ${d.error || 'Неизвестная ошибка'}. Вы можете исправить файлы и повторить загрузку.`);
                }
                if (d.status === 'waiting_manual_fix') {
                    clearInterval(pollingRef.current!);
                    setStage('fixing_errors');
                    addSystemMessage('⚠️ Автоисправление не удалось. Исправьте файлы вручную и повторите загрузку.');
                }
            } catch (e) {
                console.error('Polling error', e);
            }
        }, 2000);
    }, []);


    const handleChat = async () => {
        if (!inputValue.trim() || loading || !sessionId) return;

        const userMsg = inputValue.trim();
        setInputValue('');
        setLoading(true);

        const userEntry: ChatLogEntry = {
            id: crypto.randomUUID(),
            role: 'user',
            content: userMsg,
            timestamp: new Date().toISOString(),
            context: chatContext,
        };
        setChatLog(prev => [...prev, userEntry]);

        try {
            const res = await api.post('/ai/chat', {
                session_id: sessionId,
                message: userMsg,
                context: chatContext,
            });

            if (res.data.statement) setStatement(res.data.statement);
            if (res.data.technical_data) setTechData(prev => ({ ...(prev || {}), ...res.data.technical_data }));

            const assistantEntry: ChatLogEntry = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: res.data.response,
                timestamp: new Date().toISOString(),
                context: chatContext,
                action: res.data.action,
                updated_files: res.data.updated_files || [],
            };
            setChatLog(prev => [...prev, assistantEntry]);
        } catch {
            setChatLog(prev => [...prev, {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: '❌ Ошибка. Попробуйте ещё раз.',
                timestamp: new Date().toISOString(),
            }]);
        } finally {
            setLoading(false);
        }
    };

    const handleApproveStatement = async () => {
        if (!sessionId) return;
        setLoading(true);
        addSystemMessage('⚙️ Генерирую технические файлы...');

        try {
            const res = await api.post('/ai/approve-statement', {
                session_id: sessionId,
                problem_settings: problemSettings,
            });
            setTechData(res.data.technical_data);
            if (res.data.statement) setStatement(res.data.statement);
            setStage('files_review');

            const generated: string[] = res.data.generated_sections || [];
            const generatedNote = generated.length
                ? ` Сгенерировано: ${generated.join(', ')}.`
                : '';
            addSystemMessage(`📦 Файлы готовы!${generatedNote} Проверьте условие, затем перейдите к файлам и нажмите «Загрузить в Polygon».`);

            if (!problemSettings.tags?.length) {
                try {
                    const tagsRes = await api.post('/ai/suggest-tags', { session_id: sessionId });
                    const suggested: string[] = tagsRes.data.suggested_tags || [];
                    if (suggested.length) {
                        const updated = { ...problemSettings, tags: suggested };
                        setProblemSettings(updated);
                        setSettingsDirty(true);
                        addSystemMessage(`🏷️ Теги: ${suggested.join(', ')}`);
                    }
                } catch { /* non-critical */ }
            }

            if (!examples.length) {
                try {
                    const samplesRes = await api.post('/ai/generate-samples', { session_id: sessionId, count: 3 });
                    const newExamples: ExampleTest[] = samplesRes.data.examples || [];
                    if (newExamples.length) {
                        setExamples(newExamples);
                        addSystemMessage(`📝 Сгенерировано ${newExamples.length} примеров`);
                    }
                } catch { /* non-critical */ }
            }
        } catch (e: any) {
            addSystemMessage(`❌ Ошибка: ${e?.response?.data?.detail || e.message}`);
        } finally {
            setLoading(false);
        }
    };


    const handleSuggestTags = async () => {
        if (!sessionId) return;
        setSuggestingTags(true);
        try {
            const res = await api.post('/ai/suggest-tags', { session_id: sessionId });
            const suggested: string[] = res.data.suggested_tags || [];
            const merged = Array.from(new Set([...problemSettings.tags, ...suggested]));
            const updated = { ...problemSettings, tags: merged };
            setProblemSettings(updated);
            setSettingsDirty(true);
            addSystemMessage(`🏷️ ИИ предложил теги: ${suggested.join(', ')}`);
        } catch {
            addSystemMessage('❌ Не удалось получить теги');
        } finally {
            setSuggestingTags(false);
        }
    };

    const handleGenerateSamples = async () => {
        if (!sessionId) return;
        setGeneratingSamples(true);
        try {
            const res = await api.post('/ai/generate-samples', { session_id: sessionId, count: 3 });
            setExamples(res.data.examples || []);
            addSystemMessage(`📝 Сгенерировано ${res.data.examples?.length || 0} примеров`);
        } catch {
            addSystemMessage('❌ Не удалось сгенерировать примеры');
        } finally {
            setGeneratingSamples(false);
        }
    };

    const handleUpdateExamples = async (newExamples: ExampleTest[]) => {
        setExamples(newExamples);
        if (!sessionId) return;
        try {
            await api.patch(`/ai/session/${sessionId}/examples`, { session_id: sessionId, examples: newExamples });
        } catch { /* non-critical */ }
    };

    const handleUpdateStatementField = async (field: string, value: string) => {
        if (!sessionId) return;
        setStatement(prev => prev ? { ...prev, [field]: value } : prev);
        setEditingStatementField(null);
        try {
            await api.patch(`/ai/session/${sessionId}/statement-field`, { session_id: sessionId, field, value });
        } catch { /* non-critical */ }
    };



    const handleManualEdit = (fileKey: string) => {
        setEditingFile(fileKey);
        setEditContent(techData?.[fileKey] || '');
    };

    const handleSaveManualEdit = async () => {
        if (!editingFile || !sessionId) return;

        setTechData(prev => prev ? { ...prev, [editingFile]: editContent } : prev);

        try {
            await api.post('/ai/manual-fix-file', { session_id: sessionId, file_key: editingFile, new_content: editContent });
            setUploadErrors(prev => {
                if (!prev) return prev;
                const updated = { ...prev };
                delete updated[editingFile!];
                return Object.keys(updated).length ? updated : null;
            });
            addSystemMessage(`💾 ${getFileLabel(editingFile)} сохранён.`);
        } catch {
            addSystemMessage('⚠️ Сохранено локально, но не удалось отправить на сервер.');
        }

        setEditingFile(null);
    };


    const handleAddCustomSolution = async (tag: string, name: string) => {
        if (!sessionId) return;
        setShowAddSolution(false);
        try {
            const res = await api.post('/ai/add-custom-solution', { session_id: sessionId, tag, name });
            setSolutionMeta(res.data.solution_meta || {});
            setTechData(prev => ({ ...(prev || {}), [res.data.file_type]: '' }));
            setSelectedFile(res.data.file_type);
            setViewMode('files');
            addSystemMessage(`✅ Добавлено решение ${res.data.name} [${tag}]`);
        } catch {
            addSystemMessage('❌ Не удалось добавить решение');
        }
    };

    const handleDeleteCustomSolution = async (fileType: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!sessionId || !confirm('Удалить это решение?')) return;
        try {
            const res = await api.delete(`/ai/session/${sessionId}/solution/${fileType}`);
            setSolutionMeta(res.data.solution_meta || {});
            setTechData(prev => {
                if (!prev) return prev;
                const updated = { ...prev };
                delete updated[fileType];
                return updated;
            });
            if (selectedFile === fileType) {
                const remaining = Object.keys(techData || {}).filter(k => k !== fileType);
                setSelectedFile(remaining[0] || 'solution_cpp');
            }
            addSystemMessage('🗑️ Решение удалено');
        } catch {
            addSystemMessage('❌ Не удалось удалить решение');
        }
    };


    const handleUploadToPolygon = async () => {
        if (!sessionId) return;

        try {
            setStage('uploading');
            setUploadErrors(null);
            setProgress({ status: 'uploading', current_step: 'Запуск загрузки...' });
            await api.post('/ai/approve-files', { session_id: sessionId });
            startPolling(sessionId);
            addSystemMessage('🚀 Загрузка в Polygon...');
        } catch (e: any) {
            setStage('failed');
            setProgress({ status: 'failed', error: e?.response?.data?.detail || 'Не удалось запустить загрузку' });
            addSystemMessage('❌ Не удалось запустить загрузку.');
        }
    };

    const handleRetryUpload = async () => {
        if (!sessionId) return;

        try {
            setStage('uploading');
            setUploadErrors(null);
            setProgress({ status: 'uploading', current_step: 'Повторная загрузка...' });
            await api.post('/ai/retry-after-manual-fix', { session_id: sessionId });
            startPolling(sessionId);
            addSystemMessage('🔄 Повторная загрузка...');
        } catch {
            setStage('failed');
            addSystemMessage('❌ Не удалось повторить загрузку.');
        }
    };


    const isUploading = stage === 'uploading' || stage === 'building_package';
    const isEditable  = canEditFiles(stage);

    const allFileKeys = techData ? Object.keys(techData) : [];

    if (initialLoading) {
        return (
            <div className="flex items-center justify-center h-[calc(100vh-80px)] bg-slate-50 dark:bg-slate-950">
                <div className="text-center">
                    <Loader2 size={40} className="animate-spin text-blue-500 mx-auto mb-4" />
                    <p className="text-slate-400 font-bold">Загрузка сессии...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col lg:flex-row h-[calc(100vh-64px)] lg:gap-4 lg:p-4 p-2 bg-slate-50 dark:bg-slate-950 overflow-hidden">
            <div className={`flex-1 bg-white dark:bg-slate-900 rounded-2xl lg:rounded-3xl border border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden shadow-xl min-h-0 ${mobileTab === 'chat' ? 'hidden lg:flex' : 'flex'}`}>
                <div className="border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50">
                    <div className="p-2 lg:p-3 flex flex-wrap justify-between items-center gap-2">
                        <div className="flex items-center gap-2 lg:gap-3 min-w-0">
                            <button
                                onClick={() => navigate('/ai-tasks')}
                                className="flex items-center gap-1 lg:gap-1.5 px-2 lg:px-3 py-1.5 rounded-xl text-xs font-bold text-slate-500 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-all shrink-0"
                            >
                                <ArrowLeft size={14} /> <span className="hidden sm:inline">Назад</span>
                            </button>

                            <div className="flex bg-slate-200/50 dark:bg-slate-800 p-0.5 lg:p-1 rounded-xl overflow-x-auto">
                                <button
                                    onClick={() => setViewMode('statement')}
                                    className={`flex items-center gap-1 lg:gap-2 px-2 lg:px-4 py-1 lg:py-1.5 rounded-lg text-xs lg:text-sm font-bold transition-all whitespace-nowrap ${
                                        viewMode === 'statement' ? 'bg-white dark:bg-slate-700 shadow-sm text-blue-600' : 'text-slate-500'
                                    }`}
                                >
                                    <FileText size={14} /> Условие
                                </button>
                                <button
                                    onClick={() => setViewMode('tutorial')}
                                    className={`flex items-center gap-1 lg:gap-2 px-2 lg:px-4 py-1 lg:py-1.5 rounded-lg text-xs lg:text-sm font-bold transition-all whitespace-nowrap ${
                                        viewMode === 'tutorial' ? 'bg-white dark:bg-slate-700 shadow-sm text-blue-600' : 'text-slate-500'
                                    }`}
                                >
                                    <BookOpen size={14} /> Разбор
                                    {statement?.tutorial && <span className="w-2 h-2 bg-purple-500 rounded-full" />}
                                </button>
                                <button
                                    onClick={() => setViewMode('files')}
                                    className={`flex items-center gap-1 lg:gap-2 px-2 lg:px-4 py-1 lg:py-1.5 rounded-lg text-xs lg:text-sm font-bold transition-all whitespace-nowrap ${
                                        viewMode === 'files' ? 'bg-white dark:bg-slate-700 shadow-sm text-blue-600' : 'text-slate-500'
                                    }`}
                                >
                                    <Code size={14} /> Файлы
                                    {techData && Object.keys(techData).length > 0 && (
                                        <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                                    )}
                                </button>
                            </div>
                        </div>

                        <div className="flex items-center gap-1.5 lg:gap-2 flex-wrap justify-end">
                            {statement && stage === 'statement' && (
                                <button
                                    onClick={handleApproveStatement}
                                    disabled={loading}
                                    className="flex items-center gap-1.5 lg:gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-3 lg:px-5 py-1.5 lg:py-2 rounded-2xl text-xs lg:text-sm font-black transition-all disabled:opacity-50 shadow-lg shadow-emerald-500/20 whitespace-nowrap"
                                >
                                    {loading ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                                    <span className="hidden sm:inline">Утвердить условие</span>
                                    <span className="sm:hidden">Утвердить</span>
                                </button>
                            )}

                            {techData && stage === 'files_review' && (
                                <>
                                    <button
                                        onClick={() => setShowAddSolution(true)}
                                        className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 px-3 py-1.5 rounded-2xl text-xs lg:text-sm font-bold transition-all"
                                    >
                                        <Plus size={14} /> <span className="hidden sm:inline">Решение</span>
                                    </button>
                                    <button
                                        onClick={handleUploadToPolygon}
                                        disabled={loading}
                                        className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-3 lg:px-5 py-1.5 lg:py-2 rounded-2xl text-xs lg:text-sm font-black transition-all disabled:opacity-50 shadow-lg shadow-blue-500/20 whitespace-nowrap"
                                    >
                                        <UploadCloud size={14} />
                                        <span className="hidden sm:inline">Загрузить в Polygon</span>
                                        <span className="sm:hidden">Загрузить</span>
                                    </button>
                                </>
                            )}

                            {stage === 'failed' && techData && (
                                <button
                                    onClick={handleBackToFiles}
                                    className="flex items-center gap-1.5 bg-slate-600 hover:bg-slate-700 text-white px-3 py-1.5 rounded-2xl text-xs lg:text-sm font-bold transition-all shadow-lg whitespace-nowrap"
                                >
                                    <Edit3 size={14} />
                                    <span className="hidden sm:inline">Вернуться к файлам</span>
                                    <span className="sm:hidden">Файлы</span>
                                </button>
                            )}

                            {(stage === 'fixing_errors' || stage === 'failed') && techData && (
                                <button
                                    onClick={handleRetryUpload}
                                    className="flex items-center gap-1.5 bg-amber-500 hover:bg-amber-600 text-white px-3 lg:px-5 py-1.5 lg:py-2 rounded-2xl text-xs lg:text-sm font-black transition-all shadow-lg shadow-amber-500/20 whitespace-nowrap"
                                >
                                    <RefreshCw size={14} />
                                    <span className="hidden sm:inline">Повторить загрузку</span>
                                    <span className="sm:hidden">Повтор</span>
                                </button>
                            )}

                            {stage === 'done' && (
                                <>
                                    <button
                                        onClick={handleRetryUpload}
                                        className="flex items-center gap-1.5 bg-blue-500 hover:bg-blue-600 text-white px-3 py-1.5 rounded-2xl text-xs lg:text-sm font-bold transition-all shadow-lg"
                                    >
                                        <UploadCloud size={14} />
                                        <span className="hidden sm:inline">Дообновить</span>
                                    </button>
                                    {polygonProblemId && (
                                        <a
                                            href={`https://polygon.codeforces.com/problems/${polygonProblemId}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white px-3 lg:px-5 py-1.5 lg:py-2 rounded-2xl text-xs lg:text-sm font-black transition-all shadow-lg whitespace-nowrap"
                                        >
                                            <Package size={14} />
                                            <span className="hidden sm:inline">Открыть в Polygon</span>
                                            <span className="sm:hidden">Polygon</span>
                                        </a>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                    {sessionId && (
                        <div className="px-2 lg:px-3 pb-2 overflow-x-auto">
                            <StepBadge stage={stage} />
                        </div>
                    )}
                </div>

                <div className="flex-1 overflow-y-auto pb-14 lg:pb-0">
                    {viewMode === 'tutorial' ? (
                        <div className="p-4 lg:p-8 prose dark:prose-invert max-w-none">
                            {statement?.tutorial ? (
                                <div className="animate-in fade-in duration-500 dark:text-white">
                                    <div className="group flex items-start justify-between gap-3 mb-6">
                                        <h2 className="text-2xl font-black text-slate-800 dark:text-white flex items-center gap-2">
                                            <BookOpen size={24} className="text-purple-500" />
                                            Текстовый разбор задачи
                                        </h2>
                                        {editingStatementField !== 'tutorial' && (
                                            <button
                                                onClick={() => { setEditingStatementField('tutorial'); setStatementFieldValue(statement!.tutorial || ''); }}
                                                className="shrink-0 opacity-0 group-hover:opacity-100 flex items-center gap-1 text-xs text-slate-400 hover:text-blue-500 transition-all"
                                            >
                                                <Edit3 size={12} /> Редактировать
                                            </button>
                                        )}
                                    </div>
                                    {editingStatementField === 'tutorial' ? (
                                        <div className="space-y-2">
                                            <textarea
                                                value={statementFieldValue}
                                                onChange={e => setStatementFieldValue(e.target.value)}
                                                autoFocus
                                                className="w-full font-mono text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3 outline-none dark:text-white resize-none"
                                                rows={14}
                                            />
                                            <div className="flex gap-2">
                                                <button onClick={() => handleUpdateStatementField('tutorial', statementFieldValue)} className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-all"><Check size={12} /> Сохранить</button>
                                                <button onClick={() => setEditingStatementField(null)} className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 px-3 py-1.5 rounded-lg transition-all"><X size={12} /> Отмена</button>
                                            </div>
                                        </div>
                                    ) : (
                                        <LatexRenderer>{statement.tutorial}</LatexRenderer>
                                    )}
                                </div>
                            ) : (
                                <div className="h-full flex flex-col items-center justify-center text-slate-400 py-20">
                                    <BookOpen size={64} className="mb-4 opacity-10" />
                                    <p className="font-bold text-lg">Разбор пока не сгенерирован</p>
                                </div>
                            )}
                        </div>
                    ) : viewMode === 'statement' ? (
                        <div className="p-4 lg:p-8 prose dark:prose-invert max-w-none">
                            {statement ? (
                                <div className="animate-in fade-in duration-500 dark:text-white">
                                    <div className="group flex items-start justify-between gap-3 mb-8">
                                        {editingStatementField === 'name' ? (
                                            <div className="flex-1 space-y-2">
                                                <input
                                                    value={statementFieldValue}
                                                    onChange={e => setStatementFieldValue(e.target.value)}
                                                    autoFocus
                                                    className="w-full text-3xl font-black bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 outline-none dark:text-white"
                                                />
                                                <div className="flex gap-2">
                                                    <button onClick={() => handleUpdateStatementField('name', statementFieldValue)} className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-all"><Check size={12} /> Сохранить</button>
                                                    <button onClick={() => setEditingStatementField(null)} className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 px-3 py-1.5 rounded-lg transition-all"><X size={12} /> Отмена</button>
                                                </div>
                                            </div>
                                        ) : (
                                            <>
                                                <h1 className="text-4xl font-black text-slate-800 dark:text-white">{statement.name}</h1>
                                                <button
                                                    onClick={() => { setEditingStatementField('name'); setStatementFieldValue(statement.name); }}
                                                    className="shrink-0 opacity-0 group-hover:opacity-100 flex items-center gap-1 text-xs text-slate-400 hover:text-blue-500 transition-all mt-2"
                                                >
                                                    <Edit3 size={12} /> Редактировать
                                                </button>
                                            </>
                                        )}
                                    </div>

                                    <div className="group relative mb-4">
                                        {editingStatementField === 'legend' ? (
                                            <div className="space-y-2">
                                                <textarea
                                                    value={statementFieldValue}
                                                    onChange={e => setStatementFieldValue(e.target.value)}
                                                    autoFocus
                                                    className="w-full font-mono text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3 outline-none dark:text-white resize-none"
                                                    rows={8}
                                                />
                                                <div className="flex gap-2">
                                                    <button onClick={() => handleUpdateStatementField('legend', statementFieldValue)} className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-all"><Check size={12} /> Сохранить</button>
                                                    <button onClick={() => setEditingStatementField(null)} className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 px-3 py-1.5 rounded-lg transition-all"><X size={12} /> Отмена</button>
                                                </div>
                                            </div>
                                        ) : (
                                            <>
                                                <LatexRenderer>{statement.legend}</LatexRenderer>
                                                <button
                                                    onClick={() => { setEditingStatementField('legend'); setStatementFieldValue(statement.legend); }}
                                                    className="absolute top-0 right-0 opacity-0 group-hover:opacity-100 flex items-center gap-1 text-xs text-slate-400 hover:text-blue-500 transition-all"
                                                >
                                                    <Edit3 size={12} /> Редактировать
                                                </button>
                                            </>
                                        )}
                                    </div>

                                    <div className="group mt-8">
                                        <div className="flex items-center justify-between border-b pb-2 mb-3">
                                            <h3 className="text-xl font-bold">Входные данные</h3>
                                            {editingStatementField !== 'input' && (
                                                <button
                                                    onClick={() => { setEditingStatementField('input'); setStatementFieldValue(statement.input); }}
                                                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-blue-500 transition-colors opacity-0 group-hover:opacity-100"
                                                >
                                                    <Edit3 size={12} /> Редактировать
                                                </button>
                                            )}
                                        </div>
                                        {editingStatementField === 'input' ? (
                                            <div className="space-y-2">
                                                <textarea
                                                    value={statementFieldValue}
                                                    onChange={e => setStatementFieldValue(e.target.value)}
                                                    autoFocus
                                                    className="w-full font-mono text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3 outline-none dark:text-white resize-none"
                                                    rows={5}
                                                />
                                                <div className="flex gap-2">
                                                    <button onClick={() => handleUpdateStatementField('input', statementFieldValue)} className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-all"><Check size={12} /> Сохранить</button>
                                                    <button onClick={() => setEditingStatementField(null)} className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 px-3 py-1.5 rounded-lg transition-all"><X size={12} /> Отмена</button>
                                                </div>
                                            </div>
                                        ) : (
                                            <LatexRenderer>{statement.input}</LatexRenderer>
                                        )}
                                    </div>

                                    <div className="group mt-6">
                                        <div className="flex items-center justify-between border-b pb-2 mb-3">
                                            <h3 className="text-xl font-bold">Выходные данные</h3>
                                            {editingStatementField !== 'output' && (
                                                <button
                                                    onClick={() => { setEditingStatementField('output'); setStatementFieldValue(statement.output); }}
                                                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-blue-500 transition-colors opacity-0 group-hover:opacity-100"
                                                >
                                                    <Edit3 size={12} /> Редактировать
                                                </button>
                                            )}
                                        </div>
                                        {editingStatementField === 'output' ? (
                                            <div className="space-y-2">
                                                <textarea
                                                    value={statementFieldValue}
                                                    onChange={e => setStatementFieldValue(e.target.value)}
                                                    autoFocus
                                                    className="w-full font-mono text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3 outline-none dark:text-white resize-none"
                                                    rows={5}
                                                />
                                                <div className="flex gap-2">
                                                    <button onClick={() => handleUpdateStatementField('output', statementFieldValue)} className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-all"><Check size={12} /> Сохранить</button>
                                                    <button onClick={() => setEditingStatementField(null)} className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 px-3 py-1.5 rounded-lg transition-all"><X size={12} /> Отмена</button>
                                                </div>
                                            </div>
                                        ) : (
                                            <LatexRenderer>{statement.output}</LatexRenderer>
                                        )}
                                    </div>

                                    {statement.interaction && (
                                        <div className="group mt-6">
                                            <div className="flex items-center justify-between border-b pb-2">
                                                <h3 className="text-xl font-bold">Интерактивное взаимодействие</h3>
                                                {editingStatementField !== 'interaction' && (
                                                    <button
                                                        onClick={() => { setEditingStatementField('interaction'); setStatementFieldValue(statement.interaction || ''); }}
                                                        className="flex items-center gap-1 text-xs text-slate-400 hover:text-blue-500 transition-colors opacity-0 group-hover:opacity-100"
                                                    >
                                                        <Edit3 size={12} /> Редактировать
                                                    </button>
                                                )}
                                            </div>
                                            {editingStatementField === 'interaction' ? (
                                                <div className="mt-2 space-y-2">
                                                    <textarea value={statementFieldValue} onChange={e => setStatementFieldValue(e.target.value)} autoFocus className="w-full font-mono text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3 outline-none dark:text-white resize-none" rows={6} />
                                                    <div className="flex gap-2">
                                                        <button onClick={() => handleUpdateStatementField('interaction', statementFieldValue)} className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-all"><Check size={12} /> Сохранить</button>
                                                        <button onClick={() => setEditingStatementField(null)} className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 px-3 py-1.5 rounded-lg transition-all"><X size={12} /> Отмена</button>
                                                    </div>
                                                </div>
                                            ) : (
                                                <LatexRenderer>{statement.interaction}</LatexRenderer>
                                            )}
                                        </div>
                                    )}

                                    {statement.notes && (
                                        <div className="group mt-6">
                                            <div className="flex items-center justify-between border-b pb-2">
                                                <h3 className="text-xl font-bold">Примечания</h3>
                                                {editingStatementField !== 'notes' && (
                                                    <button
                                                        onClick={() => { setEditingStatementField('notes'); setStatementFieldValue(statement.notes || ''); }}
                                                        className="flex items-center gap-1 text-xs text-slate-400 hover:text-blue-500 transition-colors opacity-0 group-hover:opacity-100"
                                                    >
                                                        <Edit3 size={12} /> Редактировать
                                                    </button>
                                                )}
                                            </div>
                                            {editingStatementField === 'notes' ? (
                                                <div className="mt-2 space-y-2">
                                                    <textarea value={statementFieldValue} onChange={e => setStatementFieldValue(e.target.value)} autoFocus className="w-full font-mono text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3 outline-none dark:text-white resize-none" rows={4} />
                                                    <div className="flex gap-2">
                                                        <button onClick={() => handleUpdateStatementField('notes', statementFieldValue)} className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-all"><Check size={12} /> Сохранить</button>
                                                        <button onClick={() => setEditingStatementField(null)} className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 px-3 py-1.5 rounded-lg transition-all"><X size={12} /> Отмена</button>
                                                    </div>
                                                </div>
                                            ) : (
                                                <LatexRenderer>{statement.notes}</LatexRenderer>
                                            )}
                                        </div>
                                    )}

                                    {(statement.scoring || problemSettings.enable_groups || problemSettings.enable_points) && (
                                        <div className="group mt-6">
                                            <div className="flex items-center justify-between border-b pb-2">
                                                <h3 className="text-xl font-bold">Система оценки</h3>
                                                {editingStatementField !== 'scoring' && (
                                                    <button
                                                        onClick={() => { setEditingStatementField('scoring'); setStatementFieldValue(statement!.scoring || ''); }}
                                                        className="flex items-center gap-1 text-xs text-slate-400 hover:text-blue-500 transition-colors opacity-0 group-hover:opacity-100"
                                                    >
                                                        <Edit3 size={12} /> Редактировать
                                                    </button>
                                                )}
                                            </div>
                                            {editingStatementField === 'scoring' ? (
                                                <EditableScoringTable
                                                    latex={statement.scoring || ''}
                                                    onSave={val => handleUpdateStatementField('scoring', val)}
                                                    onCancel={() => setEditingStatementField(null)}
                                                />
                                            ) : statement.scoring ? (
                                                <LaTeXTable latex={statement.scoring} />
                                            ) : (
                                                <button
                                                    onClick={() => { setEditingStatementField('scoring'); setStatementFieldValue(''); }}
                                                    className="mt-3 flex items-center gap-2 text-xs text-blue-500 hover:text-blue-700 transition-colors"
                                                >
                                                    <Plus size={12} /> Добавить таблицу оценки
                                                </button>
                                            )}
                                        </div>
                                    )}

                                    <ExamplesPanel examples={examples} onUpdate={handleUpdateExamples} />
                                </div>
                            ) : (
                                <div className="h-full flex flex-col items-center justify-center text-slate-400 py-20">
                                    <Sparkles size={64} className="mb-4 opacity-10" />
                                    <p className="font-bold text-lg">Загрузка условия...</p>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="flex h-full">
                            <div className="w-28 sm:w-36 lg:w-48 border-r dark:border-slate-800 p-1 lg:p-2 flex flex-col gap-1 bg-slate-50/30 dark:bg-slate-900/30 overflow-y-auto shrink-0">
                                {techData && Object.keys(techData).length > 0 ? (
                                    <>
                                        {allFileKeys.map(key => {
                                            const hasError = uploadErrors?.[key];
                                            const isCustom = !!solutionMeta[key];
                                            return (
                                                <button
                                                    key={key}
                                                    onClick={() => { setSelectedFile(key); setEditingFile(null); }}
                                                    className={`
                                                        text-left px-3 py-2 rounded-lg text-xs font-bold truncate
                                                        transition-all flex items-center justify-between
                                                        ${selectedFile === key
                                                        ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600'
                                                        : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'}
                                                    `}
                                                >
                                                    <span className="truncate">{getFileLabel(key)}</span>
                                                    <div className="flex items-center gap-1 shrink-0">
                                                        {isCustom && (
                                                            <span className="text-[8px] font-black px-1 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-500 rounded">
                                                                {solutionMeta[key].tag}
                                                            </span>
                                                        )}
                                                        {hasError && <AlertTriangle size={12} className="text-amber-500" />}
                                                        {isCustom && (
                                                            <button
                                                                onClick={e => handleDeleteCustomSolution(key, e)}
                                                                className="opacity-0 group-hover:opacity-100 text-slate-300 hover:text-red-400 transition-all"
                                                                title="Удалить"
                                                            >
                                                                <Trash2 size={11} />
                                                            </button>
                                                        )}
                                                    </div>
                                                </button>
                                            );
                                        })}
                                        {canEditFiles(stage) && (
                                            <button
                                                onClick={() => setShowAddSolution(true)}
                                                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold text-slate-400 hover:text-blue-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all mt-1"
                                            >
                                                <Plus size={12} /> Решение
                                            </button>
                                        )}
                                    </>
                                ) : (
                                    <div className="p-4 text-center text-xs text-slate-400">
                                        Файлы появятся после утверждения условия
                                    </div>
                                )}
                            </div>
                            <div className="flex-1 flex flex-col overflow-hidden">
                                {techData && techData[selectedFile] !== undefined ? (
                                    <>
                                        <div className="flex items-center gap-2 px-4 py-2 border-b dark:border-slate-700 bg-slate-900 text-slate-400">
                                            <span className="text-xs font-mono font-bold text-slate-300">
                                                {getFileLabel(selectedFile)}
                                            </span>
                                            {solutionMeta[selectedFile] && (
                                                <span className="text-[10px] font-black px-1.5 py-0.5 bg-purple-900/50 text-purple-400 rounded">
                                                    [{solutionMeta[selectedFile].tag}]
                                                </span>
                                            )}

                                            {uploadErrors?.[selectedFile] && (
                                                <div className="ml-2 flex items-center gap-1.5 text-amber-400 text-xs bg-amber-900/20 px-2 py-1 rounded-lg">
                                                    <AlertTriangle size={12} />
                                                    <span className="truncate max-w-xs">{uploadErrors[selectedFile].error}</span>
                                                </div>
                                            )}

                                            <div className="ml-auto flex items-center gap-2">
                                                {isEditable && (
                                                    <button
                                                        onClick={() => handleManualEdit(selectedFile)}
                                                        className="flex items-center gap-1 text-xs hover:text-white transition-colors"
                                                    >
                                                        <Edit3 size={14} /> Редактировать
                                                    </button>
                                                )}
                                                {solutionMeta[selectedFile] && (
                                                    <button
                                                        onClick={e => handleDeleteCustomSolution(selectedFile, e)}
                                                        className="flex items-center gap-1 text-xs text-slate-500 hover:text-red-400 transition-colors"
                                                        title="Удалить решение"
                                                    >
                                                        <Trash2 size={14} />
                                                    </button>
                                                )}
                                            </div>
                                        </div>

                                        {editingFile === selectedFile ? (
                                            <div className="flex-1 flex flex-col bg-slate-950">
                                                <textarea
                                                    value={editContent}
                                                    onChange={e => setEditContent(e.target.value)}
                                                    className="flex-1 w-full bg-transparent text-slate-200 font-mono text-sm p-4 outline-none resize-none"
                                                    spellCheck={false}
                                                />
                                                <div className="flex gap-2 p-2 border-t dark:border-slate-700 bg-slate-900">
                                                    <button
                                                        onClick={handleSaveManualEdit}
                                                        className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-all"
                                                    >
                                                        <Check size={12} /> Сохранить
                                                    </button>
                                                    <button
                                                        onClick={() => setEditingFile(null)}
                                                        className="flex items-center gap-1 text-xs text-slate-400 hover:text-white px-3 py-1.5 rounded-lg transition-all"
                                                    >
                                                        <X size={12} /> Отмена
                                                    </button>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="flex-1 overflow-auto">
                                                {techData[selectedFile] ? (
                                                    <SyntaxHighlighter
                                                        language={getFileLang(selectedFile)}
                                                        style={vscDarkPlus}
                                                        customStyle={{ margin: 0, borderRadius: 0, height: '100%', fontSize: '0.8125rem' }}
                                                        showLineNumbers
                                                        wrapLongLines={false}
                                                    >
                                                        {techData[selectedFile]}
                                                    </SyntaxHighlighter>
                                                ) : (
                                                    <div className="flex-1 flex items-center justify-center text-slate-500 italic text-sm bg-slate-950 h-full">
                                                        Файл пуст — используйте чат справа для генерации
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </>
                                ) : (
                                    <div className="flex-1 flex items-center justify-center text-slate-600 italic text-sm bg-slate-950">
                                        Выберите файл из списка слева
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <div className={`lg:w-80 xl:w-96 flex flex-col gap-3 flex-shrink-0 min-h-0 ${mobileTab === 'chat' ? 'flex flex-1' : 'hidden lg:flex'}`}>
                <div className="flex-1 bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden shadow-sm">
                    <div className="p-3 border-b dark:border-slate-800 flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                            <Terminal size={16} className="text-blue-500 shrink-0" />
                            {techData && stage !== 'statement' ? (
                                <select
                                    value={chatContext}
                                    onChange={e => setChatContext(e.target.value)}
                                    className="text-xs font-bold bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1 text-slate-700 dark:text-slate-200 outline-none cursor-pointer min-w-0"
                                >
                                    <option value="task">🗂️ Вся задача</option>
                                    <option value="statement">📝 Условие</option>
                                    {allFileKeys.map(key => (
                                        <option key={key} value={key}>{getFileLabel(key)}</option>
                                    ))}
                                </select>
                            ) : (
                                <span className="font-black text-xs uppercase tracking-widest text-slate-700 dark:text-slate-200 truncate">
                                    {stage === 'statement' ? 'Условие' : 'AI Agent'}
                                </span>
                            )}
                        </div>
                        <select
                            value={sessionModel}
                            onChange={e => handleModelChange(e.target.value)}
                            className="text-[10px] bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1 text-slate-600 dark:text-slate-300 outline-none cursor-pointer shrink-0"
                        >
                            {AI_MODELS.map(m => (
                                <option key={m.id} value={m.id}>{m.name}</option>
                            ))}
                        </select>
                    </div>

                    <>
                        <div className="flex-1 overflow-y-auto p-4 space-y-3">
                            {chatContext === 'statement' && (
                                <ProblemSettingsPanel
                                    settings={problemSettings}
                                    onChange={handleSettingsChange}
                                    onSuggestTags={handleSuggestTags}
                                    onGenerateSamples={handleGenerateSamples}
                                    sessionId={sessionId}
                                    suggestingTags={suggestingTags}
                                    generatingSamples={generatingSamples}
                                />
                            )}

                            {chatLog.length === 0 && (
                                <div className="text-center text-slate-400 text-xs py-8">
                                    <Sparkles size={32} className="mx-auto mb-2 opacity-20" />
                                    {stage === 'statement'
                                        ? (statement ? 'Предложите правки к условию' : 'Опишите идею задачи, чтобы начать')
                                        : 'Опишите, что изменить — ИИ обновит нужные файлы или ответит на вопрос'}
                                </div>
                            )}

                            {chatLog.map(entry => (
                                <div key={entry.id} className={`flex ${entry.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                    {entry.role === 'system' ? (
                                        <div className="w-full text-center">
                                            <span className="text-[10px] text-slate-400 bg-slate-100 dark:bg-slate-800 px-3 py-1 rounded-full">
                                                {entry.content}
                                            </span>
                                        </div>
                                    ) : (
                                        <div className={`max-w-[90%] flex flex-col gap-1.5 ${entry.role === 'user' ? 'items-end' : 'items-start'}`}>
                                            {entry.role === 'user' && entry.context && (
                                                <span className="text-[10px] text-slate-400 dark:text-slate-500 px-1">
                                                    {entry.context === 'statement' ? '📝 Условие'
                                                        : entry.context === 'task' ? '🗂️ Вся задача'
                                                        : `📄 ${getFileLabel(entry.context)}`}
                                                </span>
                                            )}
                                            <div className={`px-4 py-2.5 rounded-2xl text-sm
                                                ${entry.role === 'user'
                                                    ? 'bg-blue-600 text-white shadow-md rounded-br-sm'
                                                    : 'bg-slate-100 dark:bg-slate-800 dark:text-slate-200 rounded-bl-sm'}`}>
                                                {entry.role === 'user' ? entry.content : (
                                                    <ReactMarkdown
                                                        remarkPlugins={[remarkMath]}
                                                        rehypePlugins={[rehypeKatex]}
                                                        components={{
                                                            code({ className, children, ...props }) {
                                                                const match = /language-(\w+)/.exec(className || '');
                                                                const inline = !match;
                                                                return inline ? (
                                                                    <code className="bg-slate-700 dark:bg-slate-600 text-fuchsia-300 px-1 py-0.5 rounded text-xs font-mono" {...props}>
                                                                        {children}
                                                                    </code>
                                                                ) : (
                                                                    <SyntaxHighlighter
                                                                        style={vscDarkPlus}
                                                                        language={match[1]}
                                                                        PreTag="div"
                                                                        className="rounded-lg text-xs my-2 overflow-x-auto"
                                                                    >
                                                                        {String(children).replace(/\n$/, '')}
                                                                    </SyntaxHighlighter>
                                                                );
                                                            },
                                                            p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                                                            ul: ({ children }) => <ul className="list-disc pl-4 mb-1 space-y-0.5">{children}</ul>,
                                                            ol: ({ children }) => <ol className="list-decimal pl-4 mb-1 space-y-0.5">{children}</ol>,
                                                            strong: ({ children }) => <strong className="font-bold">{children}</strong>,
                                                            h1: ({ children }) => <p className="font-bold text-base mb-1">{children}</p>,
                                                            h2: ({ children }) => <p className="font-bold mb-1">{children}</p>,
                                                            h3: ({ children }) => <p className="font-semibold mb-0.5">{children}</p>,
                                                        }}
                                                    >
                                                        {entry.content}
                                                    </ReactMarkdown>
                                                )}
                                            </div>
                                            {entry.updated_files && entry.updated_files.length > 0 && (
                                                <div className="flex flex-wrap gap-1">
                                                    {entry.updated_files.map(f => (
                                                        <span key={f} className="text-[10px] bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-0.5 rounded-full font-mono">
                                                            ✓ {f}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            ))}

                            {loading && (
                                <div className="flex justify-start">
                                    <div className="bg-slate-100 dark:bg-slate-800 p-3 rounded-2xl">
                                        <div className="flex gap-1">
                                            <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" />
                                            <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:0.2s]" />
                                            <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:0.4s]" />
                                        </div>
                                    </div>
                                </div>
                            )}
                            <div ref={chatEndRef} />
                        </div>

                        <div className="p-3 border-t dark:border-slate-800">
                            <div className="relative">
                                <textarea
                                    value={inputValue}
                                    onChange={e => setInputValue(e.target.value)}
                                    onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChat(); } }}
                                    placeholder={
                                        chatContext === 'statement'
                                            ? (statement ? 'Предложите правки к условию...' : 'Опишите идею задачи...')
                                            : chatContext === 'task'
                                                ? 'Опишите что изменить в задаче...'
                                                : `Спросите или попросите изменить ${getFileLabel(chatContext)}...`
                                    }
                                    className="w-full bg-slate-50 dark:bg-slate-800 border-2 border-transparent focus:border-blue-500 rounded-2xl p-3 pr-12 text-sm outline-none dark:text-white transition-all resize-none h-20 shadow-inner"
                                />
                                <button
                                    onClick={handleChat}
                                    disabled={loading || !inputValue.trim()}
                                    className="absolute right-2 bottom-2 p-2.5 bg-gradient-to-br from-violet-600 to-fuchsia-600 text-white rounded-xl hover:from-violet-700 hover:to-fuchsia-700 disabled:opacity-50 transition-all shadow-lg"
                                >
                                    <Send size={16} />
                                </button>
                            </div>
                        </div>
                    </>
                </div>

                {progress.status !== 'idle' && (
                    <div className={`
                        bg-white dark:bg-slate-900 p-3 lg:p-4 rounded-2xl lg:rounded-3xl border-2 shadow-xl
                        animate-in slide-in-from-bottom-4
                        ${progress.status === 'failed' || stage === 'fixing_errors'
                        ? 'border-amber-200 dark:border-amber-900'
                        : progress.status === 'done'
                            ? 'border-green-200 dark:border-green-900'
                            : 'border-blue-100 dark:border-blue-900'}
                    `}>
                        <div className="flex items-center justify-between mb-2">
                            <h4 className="font-black text-xs uppercase dark:text-white tracking-tighter">Polygon Sync</h4>
                            <div className="flex items-center gap-1.5">
                                {isUploading && <Loader2 size={14} className="animate-spin text-blue-500" />}
                                {progress.status === 'done' && <CheckCircle size={14} className="text-green-500" />}
                                {(progress.status === 'failed' || stage === 'fixing_errors') && <AlertCircle size={14} className="text-amber-500" />}
                                {polygonProblemId && <span className="text-[10px] text-slate-400">ID: {polygonProblemId}</span>}
                            </div>
                        </div>
                        <div className="w-full bg-slate-100 dark:bg-slate-800 h-1.5 rounded-full mb-2 overflow-hidden">
                            <div className={`h-full transition-all duration-700 ${
                                progress.status === 'failed' ? 'bg-red-500 w-full' :
                                stage === 'fixing_errors' ? 'bg-amber-500 w-3/4' :
                                progress.status === 'done' ? 'bg-green-500 w-full' :
                                'bg-blue-500 w-2/3 animate-pulse'
                            }`} />
                        </div>
                        <p className="text-[10px] font-bold text-slate-500 uppercase truncate">{progress.current_step}</p>
                        {progress.error && <p className="text-[10px] text-red-400 mt-1 font-mono break-all">{progress.error}</p>}
                        {progress.retries !== undefined && progress.retries > 0 && (
                            <p className="text-[10px] text-amber-400 mt-1">Попытка исправления: {progress.retries}/3</p>
                        )}
                        {polygonProblemId && (
                            <a
                                href="https://polygon.codeforces.com"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="mt-2 flex items-center justify-center gap-1.5 w-full py-1.5 rounded-xl text-[11px] font-bold
                                           bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white
                                           hover:from-violet-700 hover:to-fuchsia-700 transition-all"
                            >
                                <ExternalLink size={11} />
                                Открыть Polygon (ID задачи: {polygonProblemId})
                            </a>
                        )}
                    </div>
                )}
            </div>

            <div className="lg:hidden fixed bottom-0 left-0 right-0 flex border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 z-40">
                <button
                    onClick={() => setMobileTab('content')}
                    className={`flex-1 flex items-center justify-center gap-2 py-3 text-xs font-bold transition-colors ${
                        mobileTab === 'content'
                            ? 'text-blue-600 border-t-2 border-blue-500 -mt-px'
                            : 'text-slate-500'
                    }`}
                >
                    <FileText size={16} />
                    {viewMode === 'files' ? 'Файлы' : 'Условие'}
                </button>
                <button
                    onClick={() => setMobileTab('chat')}
                    className={`flex-1 flex items-center justify-center gap-2 py-3 text-xs font-bold transition-colors ${
                        mobileTab === 'chat'
                            ? 'text-blue-600 border-t-2 border-blue-500 -mt-px'
                            : 'text-slate-500'
                    }`}
                >
                    <Terminal size={16} />
                    Чат
                </button>
            </div>

            {showAddSolution && (
                <AddSolutionModal
                    onClose={() => setShowAddSolution(false)}
                    onAdd={handleAddCustomSolution}
                />
            )}
        </div>
    );
};
