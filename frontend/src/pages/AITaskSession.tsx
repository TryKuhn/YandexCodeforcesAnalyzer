// pages/AITaskSession.tsx

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Send, Sparkles, Loader2, CheckCircle, AlertCircle,
    FileText, UploadCloud, Code,
    Terminal, RefreshCw, Edit3, Check, X, Package,
    AlertTriangle, ChevronRight, ArrowLeft
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { api } from '../api/instance';
import { useAISettings } from '../components/layout/MainLayout';

// ─────────────────────────── Константы ──────────────────────────────────────

const FILE_LABELS: Record<string, string> = {
    validator:    'validator.cpp',
    generator:    'generator.cpp',
    checker:      'checker.cpp',
    solution_cpp: 'solution.cpp',
    solution_py:  'solution.py',
    wa_sol:       'wa.cpp',
    tl_sol:       'tl.cpp',
    re_sol:       're.cpp',
    ml_sol:       'ml.cpp',
    script:       'script.txt',
};

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
}

interface TechnicalData {
    validator?: string;
    generator?: string;
    checker?: string;
    solution_cpp?: string;
    solution_py?: string;
    wa_sol?: string;
    tl_sol?: string;
    re_sol?: string;
    ml_sol?: string;
    script?: string;
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

// ─────────────── Какие этапы позволяют редактировать файлы ──────────────────

const EDITABLE_STAGES: PipelineStage[] = [
    'files_review',
    'fixing_errors',
    'failed',
];

const canEditFiles = (stage: PipelineStage) =>
    EDITABLE_STAGES.includes(stage);

// ─────────────────────── StepBadge ─────────────────────────────────────────

const StepBadge = ({ stage }: { stage: PipelineStage }) => {
    const steps: { key: PipelineStage; label: string }[] = [
        { key: 'statement',        label: 'Условие' },
        { key: 'files_review',     label: 'Файлы' },
        { key: 'uploading',        label: 'Загрузка' },
        { key: 'building_package', label: 'Пакет' },
        { key: 'done',             label: 'Готово' },
    ];

    const stageOrder: Record<string, number> = {
        statement: 0,
        files_review: 1,
        uploading: 2,
        fixing_errors: 2,
        building_package: 3,
        done: 4,
        failed: -1,
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
                        <div className={`
                            flex items-center gap-1.5 px-2.5 py-1 rounded-full
                            text-[10px] font-bold transition-all
                            ${done   ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : ''}
                            ${active ? 'bg-blue-100  text-blue-700  dark:bg-blue-900/30  dark:text-blue-400'  : ''}
                            ${!done && !active ? 'bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-600' : ''}
                        `}>
                            {done && <Check size={10} />}
                            {s.label}
                        </div>
                        {i < steps.length - 1 && (
                            <ChevronRight size={10} className="text-slate-300 dark:text-slate-700" />
                        )}
                    </div>
                );
            })}
        </div>
    );
};

// ─────────────────────────── Основной компонент ──────────────────────────────

export const AITaskSession = () => {
    const { sessionId: urlSessionId } = useParams<{ sessionId: string }>();
    const navigate = useNavigate();
    const { load: loadSettings } = useAISettings();

    const [_selectedModel, setSelectedModel] = useState(() => loadSettings().model);
    const [_systemPrompt, setSystemPrompt]   = useState(() => loadSettings().systemPrompt);

    const [messages, setMessages]   = useState<{ role: 'user' | 'assistant' | 'system'; content: string }[]>([]);
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

    const [viewMode, setViewMode]             = useState<'statement' | 'files'>('statement');
    const [selectedFile, setSelectedFile]     = useState<keyof TechnicalData>('solution_cpp');
    const [editingFile, setEditingFile]       = useState<string | null>(null);
    const [editContent, setEditContent]       = useState('');
    const [fileRefeedback, setFileRefeedback] = useState('');
    const [refiningFile, setRefiningFile]     = useState<string | null>(null);

    const chatEndRef = useRef<HTMLDivElement>(null);
    const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // ── Автоскролл ──
    useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

    // ── Загрузка сессии ──
    useEffect(() => {
        if (!urlSessionId) { setInitialLoading(false); return; }

        api.get(`/ai/session/${urlSessionId}`)
            .then(res => {
                const d = res.data;
                setSessionId(d.session_id);
                setStage(d.stage);
                setStatement(d.statement);
                setTechData(d.technical_data);
                setSelectedModel(d.model);
                setSystemPrompt(d.system_prompt || '');
                setProgress(d.progress || { status: 'idle' });
                if (d.upload_errors && Object.keys(d.upload_errors).length)
                    setUploadErrors(d.upload_errors);
                if (d.polygon_problem_id)
                    setPolygonProblemId(d.polygon_problem_id);
                if (d.technical_data)
                    setViewMode('files');

                // Возобновляем поллинг
                if (d.stage === 'uploading' || d.stage === 'building_package')
                    startPolling(d.session_id);

                addSystemMessage(`Сессия загружена. Этап: ${stageLabel(d.stage)}`);
            })
            .catch(() => {
                addSystemMessage('❌ Сессия не найдена');
                setTimeout(() => navigate('/ai-tasks'), 2000);
            })
            .finally(() => setInitialLoading(false));
    }, [urlSessionId]);

    useEffect(() => {
        const handler = () => {
            const s = loadSettings();
            setSelectedModel(s.model);
            setSystemPrompt(s.systemPrompt);
        };
        window.addEventListener('storage', handler);
        return () => window.removeEventListener('storage', handler);
    }, []);

    useEffect(() => () => { if (pollingRef.current) clearInterval(pollingRef.current); }, []);

    // ─────────────────── Helpers ────────────────────────────────────────────

    const stageLabel = (s: PipelineStage) => ({
        statement:        'Работа с условием',
        files_review:     'Проверка файлов',
        uploading:        'Загрузка в Polygon',
        fixing_errors:    'Исправление ошибок',
        building_package: 'Сборка пакета',
        done:             'Готово',
        failed:           'Ошибка',
    }[s] || s);

    const addSystemMessage = (content: string) =>
        setMessages(prev => [...prev, { role: 'system', content }]);

    // ── Перевод failed → files_review для ручной правки ──
    const handleBackToFiles = () => {
        setStage('files_review');
        setViewMode('files');
        setProgress({ status: 'idle' });
        addSystemMessage('📝 Вернулись к редактированию файлов. Исправьте и повторите загрузку.');
    };

    // ─────────────────── Поллинг ───────────────────────────────────────────

    const startPolling = useCallback((sid: string) => {
        if (pollingRef.current) clearInterval(pollingRef.current);

        pollingRef.current = setInterval(async () => {
            try {
                const res = await api.get(`/ai/upload-progress/${sid}`);
                const d = res.data;

                setProgress({
                    status:       d.status,
                    current_step: d.current_step,
                    error:        d.error,
                    retries:      d.retries,
                });

                if (d.stage) setStage(d.stage);
                if (d.technical_data) setTechData(d.technical_data);
                if (d.upload_errors && Object.keys(d.upload_errors).length)
                    setUploadErrors(d.upload_errors);
                if (d.polygon_problem_id)
                    setPolygonProblemId(d.polygon_problem_id);

                // ── Готово ──
                if (d.status === 'done') {
                    clearInterval(pollingRef.current!);
                    addSystemMessage(`✅ Задача создана! ID: ${d.polygon_problem_id}`);
                }

                // ── Ошибка ──
                if (d.status === 'failed') {
                    clearInterval(pollingRef.current!);

                    // Не блокируем — разрешаем вернуться к файлам
                    addSystemMessage(
                        `❌ Ошибка: ${d.error || 'Неизвестная ошибка'}. ` +
                        'Вы можете исправить файлы и повторить загрузку.'
                    );
                }

                // ── Ожидание ручного фикса ──
                if (d.status === 'waiting_manual_fix') {
                    clearInterval(pollingRef.current!);
                    setStage('fixing_errors');
                    addSystemMessage(
                        '⚠️ Автоисправление не удалось. ' +
                        'Исправьте файлы вручную и повторите загрузку.'
                    );
                }
            } catch (e) {
                console.error('Polling error', e);
            }
        }, 2000);
    }, []);

    // ─────────────────── Работа с условием ──────────────────────────────────

    const handleSendMessage = async () => {
        if (!inputValue.trim() || loading) return;

        const userMsg = inputValue.trim();
        setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
        setInputValue('');
        setLoading(true);

        try {
            if (stage === 'statement' && sessionId) {
                const res = await api.post('/ai/refine-statement', {
                    session_id: sessionId,
                    feedback: userMsg,
                });
                setStatement(res.data.statement);
                setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: '✏️ Обновил условие. Проверьте.',
                }]);
            }
        } catch {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: '❌ Ошибка. Попробуйте ещё раз.',
            }]);
        } finally {
            setLoading(false);
        }
    };

    // ─────────────────── Одобрение условия ──────────────────────────────────

    const handleApproveStatement = async () => {
        if (!sessionId) return;
        setLoading(true);
        addSystemMessage('⚙️ Генерирую технические файлы...');

        try {
            const res = await api.post('/ai/approve-statement', { session_id: sessionId });
            setTechData(res.data.technical_data);
            setStage('files_review');
            setViewMode('files');
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: '📦 Файлы готовы! Проверьте и нажмите «Загрузить в Polygon».',
            }]);
        } catch (e: any) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: `❌ Ошибка: ${e?.response?.data?.detail || e.message}`,
            }]);
        } finally {
            setLoading(false);
        }
    };

    // ─────────────────── Правка файлов ──────────────────────────────────────

    const handleRefineFile = async (fileKey: string) => {
        if (!sessionId || !fileRefeedback.trim()) return;
        setRefiningFile(fileKey);

        try {
            const res = await api.post('/ai/refine-file', {
                session_id: sessionId,
                file_key: fileKey,
                feedback: fileRefeedback,
            });
            setTechData(prev => prev ? { ...prev, [fileKey]: res.data.new_code } : prev);
            setFileRefeedback('');
            addSystemMessage(`✅ ${FILE_LABELS[fileKey] || fileKey} обновлён через ИИ.`);
        } catch {
            addSystemMessage('❌ Не удалось обновить файл.');
        } finally {
            setRefiningFile(null);
        }
    };

    const handleManualEdit = (fileKey: string) => {
        setEditingFile(fileKey);
        setEditContent(techData?.[fileKey as keyof TechnicalData] || '');
    };

    const handleSaveManualEdit = async () => {
        if (!editingFile || !techData || !sessionId) return;

        const newTechData = { ...techData, [editingFile]: editContent };
        setTechData(newTechData);

        // Всегда сохраняем на сервер
        try {
            await api.post('/ai/manual-fix-file', {
                session_id: sessionId,
                file_key: editingFile,
                new_content: editContent,
            });

            // Снимаем ошибку для этого файла если была
            setUploadErrors(prev => {
                if (!prev) return prev;
                const updated = { ...prev };
                delete updated[editingFile!];
                return Object.keys(updated).length ? updated : null;
            });

            addSystemMessage(`💾 ${FILE_LABELS[editingFile] || editingFile} сохранён.`);
        } catch {
            addSystemMessage('⚠️ Сохранено локально, но не удалось отправить на сервер.');
        }

        setEditingFile(null);
    };

    // ─────────────────── Загрузка в Polygon ─────────────────────────────────

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
            setProgress({
                status: 'failed',
                error: e?.response?.data?.detail || 'Не удалось запустить загрузку',
            });
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

    // ─────────────────────────── Рендер ─────────────────────────────────────

    const isUploading = stage === 'uploading' || stage === 'building_package';
    const isEditable  = canEditFiles(stage);

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
        <div className="flex h-[calc(100vh-80px)] gap-4 p-4 bg-slate-50 dark:bg-slate-950 overflow-hidden">

            {/* ── Центральная часть ── */}
            <div className="flex-1 bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden shadow-xl">

                {/* Хедер */}
                <div className="p-3 border-b border-slate-100 dark:border-slate-800 flex flex-wrap justify-between items-center gap-2 bg-slate-50/50 dark:bg-slate-800/50">
                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => navigate('/ai-tasks')}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold text-slate-500 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
                        >
                            <ArrowLeft size={14} /> Назад
                        </button>

                        <div className="flex bg-slate-200/50 dark:bg-slate-800 p-1 rounded-xl">
                            <button
                                onClick={() => setViewMode('statement')}
                                className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-bold transition-all ${
                                    viewMode === 'statement'
                                        ? 'bg-white dark:bg-slate-700 shadow-sm text-blue-600'
                                        : 'text-slate-500'
                                }`}
                            >
                                <FileText size={16} /> Условие
                            </button>
                            <button
                                onClick={() => setViewMode('files')}
                                className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-bold transition-all ${
                                    viewMode === 'files'
                                        ? 'bg-white dark:bg-slate-700 shadow-sm text-blue-600'
                                        : 'text-slate-500'
                                }`}
                            >
                                <Code size={16} /> Файлы
                                {techData && <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />}
                            </button>
                        </div>

                        {sessionId && <StepBadge stage={stage} />}
                    </div>

                    <div className="flex items-center gap-2">
                        {/* Утвердить условие */}
                        {statement && stage === 'statement' && (
                            <button
                                onClick={handleApproveStatement}
                                disabled={loading}
                                className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-2 rounded-2xl text-sm font-black transition-all disabled:opacity-50 shadow-lg shadow-emerald-500/20"
                            >
                                {loading ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
                                Утвердить условие
                            </button>
                        )}

                        {/* Загрузить в Polygon — для files_review */}
                        {techData && stage === 'files_review' && (
                            <button
                                onClick={handleUploadToPolygon}
                                disabled={loading}
                                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-2xl text-sm font-black transition-all disabled:opacity-50 shadow-lg shadow-blue-500/20"
                            >
                                <UploadCloud size={16} />
                                Загрузить в Polygon
                            </button>
                        )}

                        {/* Вернуться к файлам — при failed */}
                        {stage === 'failed' && techData && (
                            <button
                                onClick={handleBackToFiles}
                                className="flex items-center gap-2 bg-slate-600 hover:bg-slate-700 text-white px-4 py-2 rounded-2xl text-sm font-bold transition-all shadow-lg"
                            >
                                <Edit3 size={16} />
                                Вернуться к файлам
                            </button>
                        )}

                        {/* Повторить загрузку — для fixing_errors и failed */}
                        {(stage === 'fixing_errors' || stage === 'failed') && techData && (
                            <button
                                onClick={handleRetryUpload}
                                className="flex items-center gap-2 bg-amber-500 hover:bg-amber-600 text-white px-5 py-2 rounded-2xl text-sm font-black transition-all shadow-lg shadow-amber-500/20"
                            >
                                <RefreshCw size={16} />
                                Повторить загрузку
                            </button>
                        )}

                        {/* Готово */}
                        {stage === 'done' && polygonProblemId && (
                            <a
                                href={`https://polygon.codeforces.com/problems/${polygonProblemId}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-5 py-2 rounded-2xl text-sm font-black transition-all shadow-lg"
                            >
                                <Package size={16} />
                                Открыть в Polygon
                            </a>
                        )}
                    </div>
                </div>

                {/* Контент */}
                <div className="flex-1 overflow-y-auto">
                    {viewMode === 'statement' ? (
                        <div className="p-8 prose dark:prose-invert max-w-none">
                            {statement ? (
                                <div className="animate-in fade-in duration-500 dark:text-white">
                                    <h1 className="text-4xl font-black text-slate-800 dark:text-white mb-8">
                                        {statement.name}
                                    </h1>
                                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                        {statement.legend}
                                    </ReactMarkdown>
                                    <h3 className="text-xl font-bold mt-8 border-b pb-2">Входные данные</h3>
                                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                        {statement.input}
                                    </ReactMarkdown>
                                    <h3 className="text-xl font-bold mt-6 border-b pb-2">Выходные данные</h3>
                                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                        {statement.output}
                                    </ReactMarkdown>
                                    {statement.notes && (
                                        <>
                                            <h3 className="text-xl font-bold mt-6 border-b pb-2">Примечания</h3>
                                            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                                {statement.notes}
                                            </ReactMarkdown>
                                        </>
                                    )}
                                </div>
                            ) : (
                                <div className="h-full flex flex-col items-center justify-center text-slate-400 py-20">
                                    <Sparkles size={64} className="mb-4 opacity-10" />
                                    <p className="font-bold text-lg">Загрузка условия...</p>
                                </div>
                            )}
                        </div>
                    ) : (
                        /* ── Режим файлов ── */
                        <div className="flex h-full">
                            {/* Список файлов */}
                            <div className="w-48 border-r dark:border-slate-800 p-2 flex flex-col gap-1 bg-slate-50/30 dark:bg-slate-900/30 overflow-y-auto">
                                {techData ? (
                                    Object.keys(techData).map(key => {
                                        const hasError = uploadErrors?.[key];
                                        return (
                                            <button
                                                key={key}
                                                onClick={() => { setSelectedFile(key as keyof TechnicalData); setEditingFile(null); }}
                                                className={`
                                                    text-left px-3 py-2 rounded-lg text-xs font-bold truncate
                                                    transition-all flex items-center justify-between
                                                    ${selectedFile === key
                                                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600'
                                                    : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'}
                                                `}
                                            >
                                                <span>{FILE_LABELS[key] || key}</span>
                                                {hasError && <AlertTriangle size={12} className="text-amber-500 shrink-0" />}
                                            </button>
                                        );
                                    })
                                ) : (
                                    <div className="p-4 text-center text-xs text-slate-400">
                                        Файлы появятся после утверждения условия
                                    </div>
                                )}
                            </div>

                            {/* Редактор/Просмотр кода */}
                            <div className="flex-1 flex flex-col overflow-hidden">
                                {techData && techData[selectedFile] ? (
                                    <>
                                        {/* Тулбар */}
                                        <div className="flex items-center gap-2 px-4 py-2 border-b dark:border-slate-700 bg-slate-900 text-slate-400">
                                            <span className="text-xs font-mono font-bold text-slate-300">
                                                {FILE_LABELS[selectedFile] || selectedFile}
                                            </span>

                                            {/* Ошибка для файла */}
                                            {uploadErrors?.[selectedFile] && (
                                                <div className="ml-2 flex items-center gap-1.5 text-amber-400 text-xs bg-amber-900/20 px-2 py-1 rounded-lg">
                                                    <AlertTriangle size={12} />
                                                    <span className="truncate max-w-xs">
                                                        {uploadErrors[selectedFile].error}
                                                    </span>
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
                                            </div>
                                        </div>

                                        {/* Код или редактор */}
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
                                            <div className="flex-1 bg-slate-950 p-4 font-mono text-sm overflow-auto text-slate-300">
                                                <pre><code>{techData[selectedFile]}</code></pre>
                                            </div>
                                        )}

                                        {/* Панель правки через ИИ — доступна на всех редактируемых этапах */}
                                        {isEditable && (
                                            <div className="border-t dark:border-slate-700 bg-slate-900 p-3 flex gap-2">
                                                <input
                                                    value={fileRefeedback}
                                                    onChange={e => setFileRefeedback(e.target.value)}
                                                    onKeyDown={e => {
                                                        if (e.key === 'Enter' && !e.shiftKey) {
                                                            e.preventDefault();
                                                            handleRefineFile(selectedFile);
                                                        }
                                                    }}
                                                    placeholder={`Попросить ИИ исправить ${FILE_LABELS[selectedFile] || selectedFile}...`}
                                                    className="flex-1 bg-slate-800 text-slate-200 text-xs rounded-xl px-3 py-2 outline-none border border-slate-700 focus:border-blue-500 transition-colors"
                                                />
                                                <button
                                                    onClick={() => handleRefineFile(selectedFile)}
                                                    disabled={!fileRefeedback.trim() || refiningFile === selectedFile}
                                                    className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-3 py-2 rounded-xl text-xs font-bold transition-all"
                                                >
                                                    {refiningFile === selectedFile
                                                        ? <Loader2 size={14} className="animate-spin" />
                                                        : <Sparkles size={14} />
                                                    }
                                                    Исправить
                                                </button>
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

            {/* ── Правая часть: Чат + Прогресс ── */}
            <div className="w-95 flex flex-col gap-3">

                {/* Чат */}
                <div className="flex-1 bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden shadow-sm">
                    <div className="p-4 border-b dark:border-slate-800 font-black text-sm uppercase tracking-widest flex items-center gap-2 text-slate-700 dark:text-slate-200">
                        <Terminal size={18} className="text-blue-500" />
                        AI Agent
                    </div>

                    <div className="flex-1 overflow-y-auto p-4 space-y-3">
                        {messages.length === 0 && (
                            <div className="text-center text-slate-400 text-xs py-8">
                                <Sparkles size={32} className="mx-auto mb-2 opacity-20" />
                                Работаем с задачей
                            </div>
                        )}
                        {messages.map((m, i) => (
                            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                {m.role === 'system' ? (
                                    <div className="w-full text-center">
                                        <span className="text-[10px] text-slate-400 bg-slate-100 dark:bg-slate-800 px-3 py-1 rounded-full">
                                            {m.content}
                                        </span>
                                    </div>
                                ) : (
                                    <div className={`
                                        max-w-[90%] px-4 py-2.5 rounded-2xl text-sm
                                        ${m.role === 'user'
                                        ? 'bg-blue-600 text-white shadow-md rounded-br-sm'
                                        : 'bg-slate-100 dark:bg-slate-800 dark:text-slate-200 rounded-bl-sm'}
                                    `}>
                                        {m.content}
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

                    {/* Инпут */}
                    <div className="p-3 border-t dark:border-slate-800">
                        {stage === 'statement' ? (
                            <div className="relative">
                                <textarea
                                    value={inputValue}
                                    onChange={e => setInputValue(e.target.value)}
                                    onKeyDown={e => {
                                        if (e.key === 'Enter' && !e.shiftKey) {
                                            e.preventDefault();
                                            handleSendMessage();
                                        }
                                    }}
                                    placeholder="Предложите правки к условию..."
                                    className="w-full bg-slate-50 dark:bg-slate-800 border-2 border-transparent focus:border-blue-500 rounded-2xl p-3 pr-12 text-sm outline-none dark:text-white transition-all resize-none h-20 shadow-inner"
                                />
                                <button
                                    onClick={handleSendMessage}
                                    disabled={loading || !inputValue.trim()}
                                    className="absolute right-2 bottom-2 p-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-all shadow-lg"
                                >
                                    <Send size={16} />
                                </button>
                            </div>
                        ) : (
                            <div className="text-center text-xs text-slate-400 py-2">
                                {isEditable && 'Используйте панель правки в редакторе файлов'}
                                {isUploading && 'Загрузка в процессе...'}
                                {stage === 'done' && '🎉 Задача успешно создана!'}
                            </div>
                        )}
                    </div>
                </div>

                {/* Прогресс-бар */}
                {progress.status !== 'idle' && (
                    <div className={`
                        bg-white dark:bg-slate-900 p-4 rounded-3xl border-2 shadow-xl
                        animate-in slide-in-from-bottom-4
                        ${progress.status === 'failed' || stage === 'fixing_errors'
                        ? 'border-amber-200 dark:border-amber-900'
                        : progress.status === 'done'
                            ? 'border-green-200 dark:border-green-900'
                            : 'border-blue-100 dark:border-blue-900'}
                    `}>
                        <div className="flex items-center justify-between mb-2">
                            <h4 className="font-black text-xs uppercase dark:text-white tracking-tighter">
                                Polygon Sync
                            </h4>
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

                        <p className="text-[10px] font-bold text-slate-500 uppercase truncate">
                            {progress.current_step}
                        </p>

                        {progress.error && (
                            <p className="text-[10px] text-red-400 mt-1 font-mono break-all">
                                {progress.error}
                            </p>
                        )}

                        {progress.retries !== undefined && progress.retries > 0 && (
                            <p className="text-[10px] text-amber-400 mt-1">
                                Попытка исправления: {progress.retries}/3
                            </p>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};