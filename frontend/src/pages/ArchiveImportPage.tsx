// pages/ArchiveImportPage.tsx
// Импорт архива олимпиады: загрузка zip, парсинг на бэкенде, выгрузка на Polygon
// с ИИ-генерацией чекера/валидатора и прогрессом по каждой задаче.

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Archive, Upload, Loader2, AlertCircle, CheckCircle2, XCircle,
    FileArchive, ChevronRight, Sparkles, Package,
} from 'lucide-react';
import { api } from '../api/instance';
import { AI_MODELS } from '../constants/aiModels';

const POLL_MS = 2000;

interface ProblemProgress {
    name: string;
    polygon_name: string;
    polygon_id: number | null;
    stage: string;
    error: string | null;
    solutions_total: number;
    solutions_done: number;
    tests_total: number;
    tests_done: number;
    groups_total: number;
    images_total: number;
    checker: string | null;
    validator: string | null;
    log: string[];
}

interface JobStatus {
    job_id: string;
    status: 'parsing' | 'running' | 'done' | 'error';
    error: string | null;
    archive_name: string;
    prefix: string;
    problems: ProblemProgress[];
}

const STAGE_LABEL: Record<string, string> = {
    wait:      'В очереди',
    create:    'Создание',
    statement: 'Условие',
    files:     'Файлы',
    tests:     'Тесты',
    groups:    'Группы/баллы',
    commit:    'Коммит',
    build:     'Сборка пакета',
    done:      'Готово',
    error:     'Ошибка',
};

// Порядок стадий для прогресс-бара
const STAGE_ORDER = ['create', 'statement', 'files', 'tests', 'groups', 'commit', 'build', 'done'];

const stageProgress = (stage: string): number => {
    const i = STAGE_ORDER.indexOf(stage);
    return i < 0 ? 0 : Math.round((i / (STAGE_ORDER.length - 1)) * 100);
};

// Префикс по умолчанию из имени архива (зеркалит бэкенд)
const prefixFromName = (name: string): string => {
    const stem = name.replace(/\.zip$/i, '');
    const ym = stem.match(/(\d{4})/);
    const dm = stem.match(/day\D*(\d+)/i);
    if (!ym || !dm) return '';
    return `beloi${Number(ym[1]) % 100}-${dm[1]}`;
};

export const ArchiveImportPage = () => {
    const navigate = useNavigate();

    const [file, setFile] = useState<File | null>(null);
    const [prefix, setPrefix] = useState('');
    const [prefixTouched, setPrefixTouched] = useState(false);
    const [generateAi, setGenerateAi] = useState(true);
    const [aiModel, setAiModel] = useState(AI_MODELS[1].id);
    const [buildPackage, setBuildPackage] = useState(true);

    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [job, setJob] = useState<JobStatus | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const handlePickFile = (f: File | null) => {
        setFile(f);
        setError(null);
        if (f && !prefixTouched) setPrefix(prefixFromName(f.name));
    };

    const startImport = async () => {
        if (!file || uploading) return;
        setUploading(true);
        setError(null);
        try {
            const form = new FormData();
            form.append('file', file);
            if (prefix.trim()) form.append('prefix', prefix.trim());
            form.append('generate_ai', String(generateAi));
            form.append('ai_model', aiModel);
            form.append('build_package', String(buildPackage));
            const res = await api.post('/polygon/archive/import', form, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            setJob({
                job_id: res.data.job_id,
                status: 'parsing',
                error: null,
                archive_name: file.name,
                prefix: res.data.prefix,
                problems: [],
            });
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка запуска импорта');
        } finally {
            setUploading(false);
        }
    };

    // Поллинг статуса
    useEffect(() => {
        if (!job || job.status === 'done' || job.status === 'error') {
            if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
            return;
        }
        pollRef.current = setInterval(async () => {
            try {
                const res = await api.get<JobStatus>(`/polygon/archive/import/${job.job_id}`);
                setJob(res.data);
            } catch { /* транзиентные ошибки поллинга игнорируем */ }
        }, POLL_MS);
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [job?.job_id, job?.status]);

    const reset = () => {
        setJob(null);
        setFile(null);
        setPrefixTouched(false);
        setPrefix('');
    };

    const inProgress = job && (job.status === 'parsing' || job.status === 'running');

    return (
        <div className="max-w-4xl mx-auto py-4 sm:py-6">
            {/* Header */}
            <div className="mb-6 sm:mb-8">
                <h1 className="text-2xl sm:text-3xl font-black text-slate-800 dark:text-white flex items-center gap-3">
                    <Archive className="text-blue-500" size={28} />
                    Импорт архива
                </h1>
                <p className="text-slate-500 mt-1 text-sm">
                    Загрузка архива олимпиады (Solutions / Tests / Statements) на Polygon:
                    условия из PDF с картинками, решения с тегами, тесты с группами и баллами,
                    ИИ-чекер и валидатор.
                </p>
            </div>

            {!job ? (
                /* ── Форма запуска ── */
                <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 sm:p-8 space-y-5">
                    {/* File drop */}
                    <div
                        onClick={() => fileInputRef.current?.click()}
                        onDragOver={e => e.preventDefault()}
                        onDrop={e => {
                            e.preventDefault();
                            handlePickFile(e.dataTransfer.files?.[0] ?? null);
                        }}
                        className={`cursor-pointer border-2 border-dashed rounded-2xl p-5 sm:p-8 text-center transition-all
                            ${file
                                ? 'border-blue-400 bg-blue-50/50 dark:bg-blue-900/10'
                                : 'border-slate-300 dark:border-slate-700 hover:border-blue-400 hover:bg-slate-50 dark:hover:bg-slate-800/40'
                            }`}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".zip"
                            onChange={e => handlePickFile(e.target.files?.[0] ?? null)}
                            className="hidden"
                        />
                        {file ? (
                            <div className="flex items-center justify-center gap-3 min-w-0">
                                <FileArchive size={28} className="text-blue-500 shrink-0" />
                                <div className="text-left min-w-0">
                                    <p className="font-bold text-sm dark:text-white truncate">{file.name}</p>
                                    <p className="text-xs text-slate-400">
                                        {(file.size / 1048576).toFixed(1)} МБ — нажмите, чтобы выбрать другой
                                    </p>
                                </div>
                            </div>
                        ) : (
                            <>
                                <Upload size={32} className="mx-auto mb-3 text-slate-300 dark:text-slate-600" />
                                <p className="font-bold text-sm text-slate-600 dark:text-slate-300">
                                    Перетащите .zip архив или нажмите для выбора
                                </p>
                                <p className="text-xs text-slate-400 mt-1">
                                    Внутри: Solutions.zip, Tests.zip, Statements.zip
                                </p>
                            </>
                        )}
                    </div>

                    {/* Prefix */}
                    <div>
                        <label className="block text-[11px] font-bold text-slate-500 mb-1.5">
                            Префикс имён задач на Polygon
                        </label>
                        <input
                            value={prefix}
                            onChange={e => { setPrefix(e.target.value); setPrefixTouched(true); }}
                            placeholder="beloi22-1"
                            className="w-full text-sm font-mono bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700
                                       rounded-xl px-3 py-2.5 outline-none dark:text-white focus:border-blue-500 transition-all"
                        />
                        <p className="text-[11px] text-slate-400 mt-1">
                            Задачи получат имена {prefix || 'prefix'}1, {prefix || 'prefix'}2, …
                            {!prefix && ' (определяется из имени архива, либо укажите вручную)'}
                        </p>
                    </div>

                    {/* Options */}
                    <div className="space-y-3">
                        <label className="flex items-center gap-2.5 cursor-pointer select-none">
                            <input
                                type="checkbox"
                                checked={generateAi}
                                onChange={() => setGenerateAi(v => !v)}
                                className="w-4 h-4 cursor-pointer accent-blue-500"
                            />
                            <Sparkles size={14} className="text-violet-500" />
                            <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                                Сгенерировать чекер и валидатор (ИИ)
                            </span>
                        </label>
                        {generateAi && (
                            <select
                                value={aiModel}
                                onChange={e => setAiModel(e.target.value)}
                                className="ml-6 max-w-[calc(100%-1.5rem)] truncate text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700
                                           rounded-lg px-2 py-1.5 outline-none dark:text-white"
                            >
                                {AI_MODELS.map(m => (
                                    <option key={m.id} value={m.id}>{m.name}</option>
                                ))}
                            </select>
                        )}
                        <label className="flex items-center gap-2.5 cursor-pointer select-none">
                            <input
                                type="checkbox"
                                checked={buildPackage}
                                onChange={() => setBuildPackage(v => !v)}
                                className="w-4 h-4 cursor-pointer accent-blue-500"
                            />
                            <Package size={14} className="text-blue-500" />
                            <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                                Собрать пакет после коммита
                            </span>
                        </label>
                    </div>

                    {error && (
                        <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-xl text-sm">
                            <AlertCircle size={16} />
                            {error}
                        </div>
                    )}

                    <button
                        onClick={startImport}
                        disabled={!file || uploading}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-2xl font-bold
                                   flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                    >
                        {uploading ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
                        Запустить импорт
                    </button>
                </div>
            ) : (
                /* ── Прогресс ── */
                <div className="space-y-4">
                    <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-5 flex items-center gap-3 flex-wrap">
                        <FileArchive size={20} className="text-blue-500" />
                        <div className="flex-1 min-w-0">
                            <p className="font-bold text-sm dark:text-white truncate">{job.archive_name}</p>
                            <p className="text-xs text-slate-400">префикс: <span className="font-mono">{job.prefix}</span></p>
                        </div>
                        {inProgress && (
                            <span className="flex items-center gap-2 text-xs font-bold text-blue-500">
                                <Loader2 size={14} className="animate-spin" />
                                {job.status === 'parsing' ? 'Парсинг архива...' : 'Загрузка на Polygon...'}
                            </span>
                        )}
                        {job.status === 'done' && !job.error && (
                            <span className="flex items-center gap-1.5 text-xs font-bold text-green-600 dark:text-green-400">
                                <CheckCircle2 size={14} /> Импорт завершён
                            </span>
                        )}
                        {(job.status === 'error' || (job.status === 'done' && job.error)) && (
                            <span className="flex items-center gap-1.5 text-xs font-bold text-red-500">
                                <XCircle size={14} /> {job.error || 'Ошибка'}
                            </span>
                        )}
                        {!inProgress && (
                            <button
                                onClick={reset}
                                className="px-3 py-1.5 rounded-xl text-xs font-bold bg-slate-100 dark:bg-slate-800
                                           text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
                            >
                                Новый импорт
                            </button>
                        )}
                    </div>

                    {job.status === 'parsing' && (
                        <div className="flex flex-col items-center py-12 text-slate-400">
                            <Loader2 size={28} className="animate-spin text-blue-500 mb-3" />
                            <p className="text-sm">Распаковка архива и парсинг PDF с условиями...</p>
                        </div>
                    )}

                    {job.problems.map(p => {
                        const isError = p.stage === 'error';
                        const isDone = p.stage === 'done';
                        return (
                            <div
                                key={p.name}
                                className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-4"
                            >
                                <div className="flex items-center gap-3 flex-wrap">
                                    <span className="font-black text-sm dark:text-white w-7">{p.name}</span>
                                    {p.polygon_id ? (
                                        <button
                                            onClick={() => navigate(`/tasks/${p.polygon_id}`)}
                                            className="font-mono text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-0.5"
                                        >
                                            {p.polygon_name}
                                            <ChevronRight size={12} />
                                        </button>
                                    ) : (
                                        <span className="font-mono text-xs text-slate-400">{p.polygon_name}</span>
                                    )}

                                    <div className="flex-1" />

                                    {isError ? (
                                        <span className="flex items-center gap-1.5 text-xs font-bold text-red-500">
                                            <XCircle size={13} /> Ошибка
                                        </span>
                                    ) : isDone ? (
                                        <span className="flex items-center gap-1.5 text-xs font-bold text-green-600 dark:text-green-400">
                                            <CheckCircle2 size={13} /> Готово
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1.5 text-xs font-bold text-blue-500">
                                            {p.stage !== 'wait' && <Loader2 size={12} className="animate-spin" />}
                                            {STAGE_LABEL[p.stage] || p.stage}
                                        </span>
                                    )}
                                </div>

                                {/* Progress bar */}
                                {!isError && (
                                    <div className="mt-3 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                        <div
                                            className={`h-full rounded-full transition-all duration-500 ${isDone ? 'bg-green-500' : 'bg-blue-500'}`}
                                            style={{ width: `${stageProgress(p.stage)}%` }}
                                        />
                                    </div>
                                )}

                                {/* Counters */}
                                <div className="mt-2.5 flex items-center gap-4 flex-wrap text-[11px] text-slate-500 dark:text-slate-400">
                                    {p.solutions_total > 0 && (
                                        <span>Решения: <b>{p.solutions_done}/{p.solutions_total}</b></span>
                                    )}
                                    {p.tests_total > 0 && (
                                        <span>Тесты: <b>{p.tests_done}/{p.tests_total}</b></span>
                                    )}
                                    {p.groups_total > 0 && <span>Групп: <b>{p.groups_total}</b></span>}
                                    {p.images_total > 0 && <span>Картинок: <b>{p.images_total}</b></span>}
                                    {p.checker && (
                                        <span className="text-violet-500">Чекер: <b className="font-mono">{p.checker}</b></span>
                                    )}
                                    {p.validator && (
                                        <span className="text-violet-500">Валидатор: <b className="font-mono">{p.validator}</b></span>
                                    )}
                                </div>

                                {isError && p.error && (
                                    <p className="mt-2 text-xs text-red-500 break-words">{p.error}</p>
                                )}
                                {p.log.length > 0 && (
                                    <details className="mt-2">
                                        <summary className="text-[11px] text-slate-400 cursor-pointer hover:text-slate-600 dark:hover:text-slate-300">
                                            Журнал ({p.log.length})
                                        </summary>
                                        <pre className="mt-1 text-[11px] text-slate-500 dark:text-slate-400 whitespace-pre-wrap">
                                            {p.log.join('\n')}
                                        </pre>
                                    </details>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};
