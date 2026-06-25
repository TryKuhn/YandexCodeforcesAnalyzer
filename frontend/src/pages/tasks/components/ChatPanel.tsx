// pages/tasks/components/ChatPanel.tsx

import { useState, useEffect, useRef } from 'react';
import { Send, Loader2, Bot, User, ChevronDown, FileText, BookOpen, Layers, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { api } from '../../../api/instance';
import { parseServerDate } from '../../../utils/date';
import { AI_MODELS } from '../../../constants/aiModels';

// Normalise LaTeX math delimiters so KaTeX (which expects $…$ / $$…$$) renders
// the \(…\) and \[…\] forms the models often emit.
const normalizeMath = (s: string): string =>
    s
        .replace(/\\\[/g, '$$$$').replace(/\\\]/g, '$$$$')
        .replace(/\\\(/g, '$').replace(/\\\)/g, '$');


// Targetable file contexts (file_type -> label). Generating a not-yet-existing
// file is fine — the backend creates it from scratch.
const FILE_CONTEXTS: { key: string; label: string }[] = [
    { key: 'solution_cpp', label: 'Решение (main, C++)' },
    { key: 'solution_py',  label: 'Решение (Python, OK)' },
    { key: 'tl_sol',       label: 'Решение TL (медленное)' },
    { key: 'wa_sol',       label: 'Решение WA (неверное)' },
    { key: 're_sol',       label: 'Решение RE (рантайм)' },
    { key: 'ml_sol',       label: 'Решение ML (память)' },
    { key: 'generator',    label: 'Генератор' },
    { key: 'validator',    label: 'Валидатор' },
    { key: 'checker',      label: 'Чекер' },
    { key: 'interactor',   label: 'Интерактор' },
    { key: 'scorer',       label: 'Скорер (output-only)' },
    { key: 'script',       label: 'Скрипт тестов' },
];

interface ChatMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: string;
    action?: 'modify' | 'answer';
    updated_files?: string[];
    is_error?: boolean;
    context?: { scope?: string; file_key?: string };
}

// Contextual label for the in-progress indicator (instead of a flat "Думает...").
const SCOPE_LABEL: Record<string, string> = {
    task: 'Работаю над задачей…',
    statement: 'Работаю над условием…',
    file: 'Генерирую файл…',
};
const progressLabel = (scope?: string) => SCOPE_LABEL[scope || 'task'] || SCOPE_LABEL.task;

interface Props {
    sessionId: string | null;
    model: string;
    onModelChange: (model: string) => void;
    polygonId: number;
    initialMessages?: ChatMessage[];
    onModified?: (updatedFiles: string[]) => void;
}

// Context the user is acting from (mirrors backend ChatContext).
type ContextValue = 'task' | 'statement' | `file:${string}`;

const formatTime = (ts: string) => {
    try {
        return parseServerDate(ts).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    } catch {
        return '';
    }
};

export const ChatPanel = ({ sessionId, model, onModelChange, polygonId, initialMessages = [], onModified }: Props) => {
    const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
    const [input, setInput] = useState('');
    const [sending, setSending] = useState(false);
    const [resuming, setResuming] = useState(false);
    const [context, setContext] = useState<ContextValue>('task');
    const [progress, setProgress] = useState<{
        current_step?: string; step?: number; total?: number; status?: string;
    } | null>(null);
    const bottomRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        setMessages(initialMessages);
    }, [sessionId]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Resume an in-flight operation after a page reload. The backend persists the
    // user message first and the assistant reply only once the (possibly long)
    // executor finishes. So if the last persisted message is from the user, the
    // operation is still running in the background — show the indicator again.
    useEffect(() => {
        const last = initialMessages[initialMessages.length - 1];
        setResuming(!!last && last.role === 'user');
    }, [sessionId, initialMessages]);

    // While resuming, poll the session until the assistant reply lands.
    useEffect(() => {
        if (!resuming || !polygonId) return;
        let attempts = 0;
        const MAX = 100; // ~5 min at 3s
        const timer = setInterval(async () => {
            attempts += 1;
            try {
                const res = await api.get(`/polygon/problems/${polygonId}/session`);
                const log: ChatMessage[] = res.data?.chat_log || [];
                const last = log[log.length - 1];
                if (last && last.role !== 'user') {
                    setMessages(log);
                    setResuming(false);
                    if (last.role === 'assistant' && (last.updated_files || []).length > 0) {
                        onModified?.(last.updated_files || []);
                    }
                    return;
                }
            } catch { /* transient — keep polling */ }
            if (attempts >= MAX) {
                setResuming(false);
                setMessages(prev => [...prev, {
                    id: crypto.randomUUID(),
                    role: 'system',
                    content: 'Операция выполняется дольше обычного. Обновите страницу позже, чтобы увидеть результат.',
                    timestamp: new Date().toISOString(),
                }]);
            }
        }, 3000);
        return () => clearInterval(timer);
    }, [resuming, polygonId]);

    // Label for the in-progress indicator: live send uses the selected context;
    // a resumed op reads the context stored on the pending user message.
    const lastMsg = messages[messages.length - 1];
    const liveScope = context.startsWith('file:') ? 'file' : context;
    const indicatorLabel = sending
        ? progressLabel(liveScope)
        : progressLabel(lastMsg?.context?.scope);
    const busy = sending || resuming;

    // While busy, poll the session's progress so the indicator shows the live
    // stage (Генерирую условие → файлы → сборка) and a progress bar instead of a
    // flat label. The generation request is synchronous, but it commits progress
    // at each stage, so a separate poll sees it.
    useEffect(() => {
        if (!busy || !sessionId) { setProgress(null); return; }
        const poll = async () => {
            try {
                const res = await api.get(`/ai/upload-progress/${sessionId}`);
                const d = res.data || {};
                if (d.current_step || d.status) {
                    setProgress({
                        current_step: d.current_step, step: d.step,
                        total: d.total, status: d.status,
                    });
                }
            } catch { /* transient — keep the last known step */ }
        };
        poll();
        const timer = setInterval(poll, 1500);
        return () => clearInterval(timer);
    }, [busy, sessionId]);

    // Percentage for a determinate bar (generation stages); null → indeterminate.
    const progressPct = progress?.total
        ? Math.round(((progress.step || 0) / progress.total) * 100)
        : null;
    const stepText = progress?.current_step || indicatorLabel;

    const buildContext = () => {
        if (context === 'task') return { scope: 'task' };
        if (context === 'statement') return { scope: 'statement' };
        return { scope: 'file', file_key: context.slice('file:'.length) };
    };

    const sendMessage = async () => {
        const text = input.trim();
        if (!text || sending || resuming || !sessionId) return;

        const userMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'user',
            content: text,
            timestamp: new Date().toISOString(),
        };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setSending(true);

        try {
            const res = await api.post('/ai/chat', {
                session_id: sessionId,
                message: text,
                context: buildContext(),
            });
            const data = res.data;
            // Heavy generation runs in the background: the reply isn't here yet.
            // Switch to polling — the resume loop picks it up from the chat_log.
            if (data.pending) {
                setResuming(true);
                return;
            }
            const assistantMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: data.response || '',
                timestamp: new Date().toISOString(),
                action: data.action,
                updated_files: data.synced_to_polygon ? (data.updated_files || []) : [],
                is_error: data.is_error,
            };
            setMessages(prev => [...prev, assistantMsg]);
            if (data.action === 'modify' && (data.updated_files || []).length > 0) {
                onModified?.(data.updated_files);
            }
        } catch (e: any) {
            const errMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'system',
                content: e?.response?.data?.detail || 'Ошибка отправки. Попробуйте снова.',
                timestamp: new Date().toISOString(),
            };
            setMessages(prev => [...prev, errMsg]);
        } finally {
            setSending(false);
            inputRef.current?.focus();
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    const ContextIcon = () => {
        if (context === 'statement') return <BookOpen size={11} className="text-slate-400 shrink-0" />;
        if (context.startsWith('file:')) return <FileText size={11} className="text-slate-400 shrink-0" />;
        return <Layers size={11} className="text-slate-400 shrink-0" />;
    };

    return (
        <div className="w-full min-w-0 flex flex-col border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 relative">
            {/* Header */}
            <div className="shrink-0 px-3 py-2 border-b border-slate-100 dark:border-slate-800 flex items-center gap-2">
                <Bot size={15} className="text-blue-500 shrink-0" />
                <span className="text-xs font-bold text-slate-700 dark:text-slate-200 flex-1 min-w-0 truncate">AI Агент</span>
                <div className="relative shrink-0">
                    <select
                        value={model}
                        onChange={e => onModelChange(e.target.value)}
                        className="appearance-none text-[10px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300
                                   border border-slate-200 dark:border-slate-700 rounded-lg pl-2 pr-5 py-1 outline-none
                                   cursor-pointer hover:bg-slate-200 dark:hover:bg-slate-700 transition-all max-w-[120px] truncate"
                    >
                        {AI_MODELS.map(m => (
                            <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                    </select>
                    <ChevronDown size={10} className="absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400" />
                </div>
            </div>

            {/* Context selector */}
            <div className="shrink-0 px-3 py-1.5 border-b border-slate-100 dark:border-slate-800 flex items-center gap-1.5">
                <ContextIcon />
                <span className="text-[10px] font-bold text-slate-400 shrink-0">Контекст:</span>
                <div className="relative flex-1">
                    <select
                        value={context}
                        onChange={e => setContext(e.target.value as ContextValue)}
                        className="appearance-none w-full text-[10px] font-bold bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300
                                   border border-slate-200 dark:border-slate-700 rounded-lg pl-2 pr-5 py-1 outline-none
                                   cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700 transition-all truncate"
                    >
                        <option value="task">Вся задача</option>
                        <option value="statement">Условие</option>
                        {FILE_CONTEXTS.map(c => (
                            <option key={c.key} value={`file:${c.key}`}>{c.label}</option>
                        ))}
                    </select>
                    <ChevronDown size={10} className="absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400" />
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-slate-400 text-center py-8">
                        <Bot size={32} className="mb-2 opacity-20" />
                        <p className="text-xs font-bold">AI Агент</p>
                        <p className="text-[10px] mt-1 opacity-70">
                            Задайте вопрос или попросите изменить задачу.<br/>
                            Правки сразу синхронизируются с Polygon.
                        </p>
                    </div>
                ) : (
                    messages.map(msg => (
                        <div
                            key={msg.id}
                            className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                        >
                            {msg.role !== 'user' && (
                                <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5
                                    ${msg.is_error || msg.role === 'system'
                                        ? msg.is_error ? 'bg-red-100 dark:bg-red-900/30' : 'bg-slate-100 dark:bg-slate-800'
                                        : 'bg-blue-100 dark:bg-blue-900/40'}`}>
                                    <Bot size={12} className={msg.is_error ? 'text-red-500' : msg.role === 'system' ? 'text-slate-400' : 'text-blue-500'} />
                                </div>
                            )}
                            {msg.role === 'user' && (
                                <div className="w-6 h-6 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center shrink-0 mt-0.5">
                                    <User size={12} className="text-slate-500" />
                                </div>
                            )}
                            <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs leading-relaxed
                                ${msg.role === 'user'
                                    ? 'bg-blue-600 text-white'
                                    : msg.is_error
                                        ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800'
                                        : msg.role === 'system'
                                            ? 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 italic'
                                            : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200'
                                }`}>
                                {msg.role === 'assistant' && !msg.is_error ? (
                                    <div className="prose prose-sm dark:prose-invert max-w-none break-words text-xs
                                                    prose-p:my-1 prose-headings:my-1.5 prose-ul:my-1 prose-ol:my-1 prose-li:my-0
                                                    prose-pre:my-1.5 prose-pre:bg-slate-200/70 dark:prose-pre:bg-slate-950
                                                    prose-pre:text-[11px] prose-pre:p-2 prose-pre:rounded-lg
                                                    prose-code:text-[11px] prose-code:before:content-none prose-code:after:content-none
                                                    [&_pre]:overflow-x-auto [&_pre]:whitespace-pre
                                                    [&_table]:block [&_table]:overflow-x-auto [&_table]:text-[11px]">
                                        <ReactMarkdown
                                            remarkPlugins={[remarkGfm, remarkMath]}
                                            rehypePlugins={[[rehypeKatex, { macros: { '\\texttt': '\\mathtt{#1}' } }]]}
                                        >
                                            {normalizeMath(msg.content)}
                                        </ReactMarkdown>
                                    </div>
                                ) : (
                                    <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                                )}
                                {msg.updated_files && msg.updated_files.length > 0 && (
                                    <div className="mt-1.5 flex flex-wrap items-center gap-1">
                                        <RefreshCw size={9} className="text-emerald-500" />
                                        <span className="text-[9px] font-bold text-emerald-600 dark:text-emerald-400">
                                            Синхронизировано с Polygon
                                        </span>
                                    </div>
                                )}
                                <p className={`text-[9px] mt-1 opacity-60 ${msg.role === 'user' ? 'text-right' : ''}`}>
                                    {formatTime(msg.timestamp)}
                                </p>
                            </div>
                        </div>
                    ))
                )}
                {busy && (
                    <div className="flex gap-2">
                        <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center shrink-0">
                            <Bot size={12} className="text-blue-500" />
                        </div>
                        <div className="bg-slate-100 dark:bg-slate-800 rounded-2xl px-3 py-2 flex flex-col gap-1.5 min-w-[200px]">
                            <div className="flex items-center gap-2">
                                <Loader2 size={12} className="animate-spin text-slate-400 shrink-0" />
                                <span className="text-[10px] text-slate-500 dark:text-slate-300 break-words">
                                    {stepText}
                                </span>
                                {progressPct !== null && (
                                    <span className="ml-auto text-[9px] font-bold text-slate-400 shrink-0">
                                        {progress?.step}/{progress?.total}
                                    </span>
                                )}
                            </div>
                            {/* Progress bar: determinate for generation stages,
                                animated/indeterminate while the package builds. */}
                            <div className="h-1 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                                {progressPct !== null ? (
                                    <div
                                        className="h-full bg-blue-500 transition-all duration-500"
                                        style={{ width: `${progressPct}%` }}
                                    />
                                ) : (
                                    <div className="h-full w-1/3 bg-blue-500 animate-pulse" />
                                )}
                            </div>
                        </div>
                    </div>
                )}
                <div ref={bottomRef} />
            </div>

            {/* Input area */}
            <div className="shrink-0 border-t border-slate-100 dark:border-slate-800 p-2">
                <div className="flex gap-2 items-end">
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={sessionId ? 'Сообщение... (Enter)' : 'Нет активной сессии'}
                        disabled={!sessionId || busy}
                        rows={2}
                        className="flex-1 resize-none text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700
                                   rounded-xl px-3 py-2 outline-none dark:text-white placeholder:text-slate-400
                                   focus:border-blue-500 transition-all disabled:opacity-50 min-h-[52px] max-h-32"
                    />
                    <button
                        onClick={sendMessage}
                        disabled={!input.trim() || busy || !sessionId}
                        className="flex items-center justify-center w-8 h-8 mb-0.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl
                                   disabled:opacity-40 transition-all shrink-0 active:scale-95"
                    >
                        {sending
                            ? <Loader2 size={14} className="animate-spin" />
                            : <Send size={14} />
                        }
                    </button>
                </div>
            </div>
        </div>
    );
};
