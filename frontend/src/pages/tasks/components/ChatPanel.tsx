// pages/tasks/components/ChatPanel.tsx

import { useEffect, useRef, useState } from 'react';
import { Send, Loader2, Bot, User, ChevronDown, FileText, BookOpen, Layers, RefreshCw, Square } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { parseServerDate } from '../../../utils/date';
import { AI_MODELS } from '../../../constants/aiModels';
import { RUN_LABELS, isActive, type AiMessage, type AiRun, type ChatContext } from '../../../api/ai';

// Normalise LaTeX math delimiters so KaTeX (which expects $…$ / $$…$$) renders
// the \(…\) and \[…\] forms the models often emit.
const normalizeMath = (s: string): string =>
    s
        .replace(/\\\[/g, '$$$$').replace(/\\\]/g, '$$$$')
        .replace(/\\\(/g, '$').replace(/\\\)/g, '$');

// What the user is looking at; the router uses it to pick the part to change.
const FILE_CONTEXTS: { key: string; label: string }[] = [
    { key: 'solution',   label: 'Решения' },
    { key: 'generator',  label: 'Генераторы' },
    { key: 'validator',  label: 'Валидатор' },
    { key: 'checker',    label: 'Чекер' },
    { key: 'interactor', label: 'Интерактор' },
    { key: 'script',     label: 'Скрипт тестов' },
];

const SUGGESTIONS = [
    'Объясни авторское решение',
    'Проверь, что валидатор соответствует условию',
    'Добавь тесты на крайние случаи',
    'Собери пакет',
];

type ContextValue = 'task' | 'statement' | `file:${string}`;

interface Props {
    sessionId: string | null;
    model: string;
    onModelChange: (model: string) => void;
    messages: AiMessage[];
    activeRun: AiRun | null;
    onSend: (text: string, context: ChatContext) => Promise<void>;
    onCancel: () => void;
    error?: string | null;
}

const formatTime = (ts: string | null) => {
    if (!ts) return '';
    try {
        const d = parseServerDate(ts);
        const now = new Date();
        const time = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
        if (d.toDateString() === now.toDateString()) return time;
        const date = d.toLocaleDateString('ru-RU', d.getFullYear() === now.getFullYear()
            ? { day: '2-digit', month: '2-digit' }
            : { day: '2-digit', month: '2-digit', year: 'numeric' });
        return `${date} ${time}`;
    } catch {
        return '';
    }
};

const toContext = (value: ContextValue): ChatContext => {
    if (value === 'task') return { scope: 'task' };
    if (value === 'statement') return { scope: 'statement' };
    return { scope: 'file', file_role: value.slice('file:'.length) };
};

export const ChatPanel = ({ sessionId, model, onModelChange, messages, activeRun, onSend, onCancel, error }: Props) => {
    const [input, setInput] = useState('');
    const [sending, setSending] = useState(false);
    const [sendError, setSendError] = useState<string | null>(null);
    const [context, setContext] = useState<ContextValue>('task');
    const bottomRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const didInitialScroll = useRef(false);

    const busy = sending || isActive(activeRun);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: didInitialScroll.current ? 'smooth' : 'auto' });
        didInitialScroll.current = true;
    }, [messages.length, activeRun?.step]);

    const sendMessage = async (text = input.trim()) => {
        if (!text || busy || !sessionId) return;
        setSending(true);
        setSendError(null);
        try {
            await onSend(text, toContext(context));
            setInput('');
        } catch (e: unknown) {
            const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            setSendError(detail || 'Ошибка отправки. Попробуйте снова.');
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

    const ContextIcon = context === 'statement' ? BookOpen : context.startsWith('file:') ? FileText : Layers;
    const progressPct = activeRun && activeRun.progress_total > 0
        ? Math.round((activeRun.progress_done / activeRun.progress_total) * 100)
        : null;

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
                                   cursor-pointer hover:bg-slate-200 dark:hover:bg-slate-700 transition-all max-w-[130px] truncate"
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
                <ContextIcon size={11} className="text-slate-400 shrink-0" />
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
                {error && (
                    <div className="text-[11px] text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-xl px-3 py-2">
                        {error}
                    </div>
                )}
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-slate-400 text-center py-8 gap-3">
                        <Bot size={32} className="opacity-20" />
                        <div>
                            <p className="text-xs font-bold">AI Агент</p>
                            <p className="text-[10px] mt-1 opacity-70">
                                Задайте вопрос, попросите изменить задачу<br />
                                или опишите идею — ИИ создаст задачу целиком.
                            </p>
                        </div>
                        {sessionId && (
                            <div className="flex flex-wrap justify-center gap-1.5 px-2">
                                {SUGGESTIONS.map(s => (
                                    <button
                                        key={s}
                                        onClick={() => sendMessage(s)}
                                        className="text-[10px] font-bold px-2 py-1 rounded-lg bg-slate-100 dark:bg-slate-800
                                                   text-slate-500 hover:text-blue-600 dark:hover:text-blue-400 transition-all"
                                    >
                                        {s}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                ) : (
                    messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)
                )}

                {activeRun && isActive(activeRun) && (
                    <div className="flex gap-2">
                        <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center shrink-0">
                            <Bot size={12} className="text-blue-500" />
                        </div>
                        <div className="bg-slate-100 dark:bg-slate-800 rounded-2xl px-3 py-2 flex flex-col gap-1.5 min-w-[200px] flex-1">
                            <div className="flex items-center gap-2">
                                <Loader2 size={12} className="animate-spin text-slate-400 shrink-0" />
                                <span className="text-[10px] font-bold text-slate-500 dark:text-slate-300 shrink-0">
                                    {RUN_LABELS[activeRun.kind]}:
                                </span>
                                <span className="text-[10px] text-slate-500 dark:text-slate-300 break-words flex-1 min-w-0">
                                    {activeRun.status === 'queued' ? 'в очереди' : activeRun.step || '…'}
                                </span>
                                {progressPct !== null && (
                                    <span className="text-[9px] font-bold text-slate-400 shrink-0">
                                        {activeRun.progress_done}/{activeRun.progress_total}
                                    </span>
                                )}
                                <button
                                    onClick={onCancel}
                                    title="Отменить"
                                    className="shrink-0 text-slate-400 hover:text-red-500 transition-colors"
                                >
                                    <Square size={11} />
                                </button>
                            </div>
                            <div className="h-1 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                                {progressPct !== null ? (
                                    <div className="h-full bg-blue-500 transition-all duration-500" style={{ width: `${progressPct}%` }} />
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
                {sendError && <p className="text-[10px] text-red-500 mb-1 px-1">{sendError}</p>}
                <div className="flex gap-2 items-end">
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={sessionId ? (busy ? 'ИИ работает…' : 'Сообщение... (Enter)') : 'Нет активной сессии'}
                        disabled={!sessionId || busy}
                        rows={2}
                        className="flex-1 resize-none text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700
                                   rounded-xl px-3 py-2 outline-none dark:text-white placeholder:text-slate-400
                                   focus:border-blue-500 transition-all disabled:opacity-50 min-h-[52px] max-h-32"
                    />
                    <button
                        onClick={() => sendMessage()}
                        disabled={!input.trim() || busy || !sessionId}
                        className="flex items-center justify-center w-8 h-8 mb-0.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl
                                   disabled:opacity-40 transition-all shrink-0 active:scale-95"
                    >
                        {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                    </button>
                </div>
            </div>
        </div>
    );
};

const MessageBubble = ({ msg }: { msg: AiMessage }) => {
    const isUser = msg.role === 'user';
    const changed = msg.meta?.changed || [];
    return (
        <div className={`flex gap-2 ${isUser ? 'flex-row-reverse' : ''}`}>
            {isUser ? (
                <div className="w-6 h-6 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center shrink-0 mt-0.5">
                    <User size={12} className="text-slate-500" />
                </div>
            ) : (
                <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5
                    ${msg.is_error ? 'bg-red-100 dark:bg-red-900/30'
                        : msg.role === 'system' ? 'bg-slate-100 dark:bg-slate-800' : 'bg-blue-100 dark:bg-blue-900/40'}`}>
                    <Bot size={12} className={msg.is_error ? 'text-red-500' : msg.role === 'system' ? 'text-slate-400' : 'text-blue-500'} />
                </div>
            )}
            <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs leading-relaxed
                ${isUser
                    ? 'bg-blue-600 text-white'
                    : msg.is_error
                        ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800'
                        : msg.role === 'system'
                            ? 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 italic'
                            : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200'
                }`}>
                {!isUser && msg.role === 'assistant' ? (
                    <div className="prose prose-sm dark:prose-invert max-w-none break-words text-xs
                                    prose-p:my-1 prose-headings:my-1.5 prose-ul:my-1 prose-ol:my-1 prose-li:my-0
                                    prose-pre:my-1.5 prose-pre:bg-slate-200/70 dark:prose-pre:bg-slate-950
                                    prose-pre:text-[11px] prose-pre:p-2 prose-pre:rounded-lg
                                    prose-code:text-[11px] prose-code:before:content-none prose-code:after:content-none
                                    [&_pre]:overflow-x-auto [&_pre]:whitespace-pre
                                    [&_table]:block [&_table]:overflow-x-auto [&_table]:text-[11px]
                                    [&_th]:px-1.5 [&_td]:px-1.5 [&_th]:text-left">
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
                {changed.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-1">
                        <RefreshCw size={9} className="text-emerald-500" />
                        <span className="text-[9px] font-bold text-emerald-600 dark:text-emerald-400">
                            Сохранено в Polygon: {changed.length}
                        </span>
                    </div>
                )}
                <p className={`text-[9px] mt-1 opacity-60 ${isUser ? 'text-right' : ''}`}>
                    {formatTime(msg.timestamp)}
                </p>
            </div>
        </div>
    );
};
