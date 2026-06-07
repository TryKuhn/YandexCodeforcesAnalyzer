// pages/tasks/components/ChatPanel.tsx

import { useState, useEffect, useRef } from 'react';
import { Send, Loader2, Bot, User, ChevronDown, Paperclip, X, FileText, TestTube, BookOpen } from 'lucide-react';
import { api } from '../../../api/instance';

const AI_MODELS = [
    { id: 'anthropic/claude-opus-4.7',     name: 'Claude Opus 4.7' },
    { id: 'anthropic/claude-sonnet-4.6',   name: 'Claude Sonnet 4.6' },
    { id: 'google/gemini-3.1-pro-preview', name: 'Gemini 3.1 Pro' },
    { id: 'openai/gpt-5.5-pro',            name: 'GPT-5.5 Pro' },
];

interface ChatMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: string;
}

interface Attachment {
    id: string;
    label: string;
    content: string;
    icon: 'file' | 'test' | 'statement';
}

interface Props {
    sessionId: string | null;
    model: string;
    onModelChange: (model: string) => void;
    polygonId: number;
    initialMessages?: ChatMessage[];
}

const formatTime = (ts: string) => {
    try {
        return new Date(ts).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    } catch {
        return '';
    }
};

type PickerMode = null | 'files' | 'tests';

interface FileEntry { name: string; section: 'source' | 'resource' | 'aux' | 'solution' }
interface TestEntry { index: number; preview: string }

export const ChatPanel = ({ sessionId, model, onModelChange, polygonId, initialMessages = [] }: Props) => {
    const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
    const [input, setInput] = useState('');
    const [sending, setSending] = useState(false);
    const [attachments, setAttachments] = useState<Attachment[]>([]);
    const [pickerMode, setPickerMode] = useState<PickerMode>(null);
    const [pickerLoading, setPickerLoading] = useState(false);
    const [files, setFiles] = useState<FileEntry[]>([]);
    const [tests, setTests] = useState<TestEntry[]>([]);
    const [loadingAttach, setLoadingAttach] = useState<string | null>(null);
    const bottomRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        setMessages(initialMessages);
    }, [sessionId]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const openFilePicker = async () => {
        if (pickerMode === 'files') { setPickerMode(null); return; }
        setPickerMode('files');
        if (files.length > 0) return;
        setPickerLoading(true);
        try {
            const res = await api.get(`/polygon/problems/${polygonId}/files`);
            const data = res.data;
            const all: FileEntry[] = [
                ...(data.solutions || []).map((f: any) => ({ name: f.name, section: 'solution' as const })),
                ...(data.sourceFiles || data.source_files || []).map((f: any) => ({ name: f.name, section: 'source' as const })),
                ...(data.resourceFiles || data.resource_files || []).map((f: any) => ({ name: f.name, section: 'resource' as const })),
                ...(data.auxFiles || data.aux_files || []).map((f: any) => ({ name: f.name, section: 'aux' as const })),
            ];
            setFiles(all);
        } catch {
            // ignore
        } finally {
            setPickerLoading(false);
        }
    };

    const openTestsPicker = async () => {
        if (pickerMode === 'tests') { setPickerMode(null); return; }
        setPickerMode('tests');
        if (tests.length > 0) return;
        setPickerLoading(true);
        try {
            const res = await api.get(`/polygon/problems/${polygonId}/tests/tests?no_inputs=false`);
            const data: any[] = res.data || [];
            setTests(data.map(t => ({
                index: t.index,
                preview: (t.input || '').slice(0, 60),
            })));
        } catch {
            // ignore
        } finally {
            setPickerLoading(false);
        }
    };

    const attachFile = async (entry: FileEntry) => {
        const key = `file-${entry.section}-${entry.name}`;
        if (attachments.some(a => a.id === key)) { setPickerMode(null); return; }
        setLoadingAttach(key);
        try {
            let content = '';
            if (entry.section === 'solution') {
                const res = await api.get(`/polygon/problems/${polygonId}/solutions/${encodeURIComponent(entry.name)}/content`);
                content = res.data.content ?? '';
            } else {
                const res = await api.get(`/polygon/problems/${polygonId}/files/content`, {
                    params: { type: entry.section, name: entry.name },
                });
                content = res.data.content ?? '';
            }
            setAttachments(prev => [...prev, {
                id: key,
                label: entry.name,
                content,
                icon: 'file',
            }]);
        } catch (e: any) {
            // attach error info as content
            setAttachments(prev => [...prev, {
                id: key,
                label: entry.name,
                content: `(ошибка загрузки: ${e?.response?.data?.detail || 'unknown'})`,
                icon: 'file',
            }]);
        } finally {
            setLoadingAttach(null);
            setPickerMode(null);
        }
    };

    const attachTest = async (t: TestEntry) => {
        const key = `test-${t.index}`;
        if (attachments.some(a => a.id === key)) { setPickerMode(null); return; }
        setLoadingAttach(key);
        try {
            const res = await api.get(`/polygon/problems/${polygonId}/tests/tests/${t.index}/input`);
            const content = res.data.content ?? '';
            setAttachments(prev => [...prev, {
                id: key,
                label: `Тест #${t.index}`,
                content,
                icon: 'test',
            }]);
        } catch {
            setAttachments(prev => [...prev, {
                id: key,
                label: `Тест #${t.index}`,
                content: t.preview || '(нет данных)',
                icon: 'test',
            }]);
        } finally {
            setLoadingAttach(null);
            setPickerMode(null);
        }
    };

    const attachStatement = async () => {
        const key = 'statement-russian';
        if (attachments.some(a => a.id === key)) return;
        setLoadingAttach(key);
        try {
            const res = await api.get(`/polygon/problems/${polygonId}/statement`);
            const data = res.data;
            const stmt = data.russian || data.english || Object.values(data)[0] || {};
            const content = [
                stmt.name && `Название: ${stmt.name}`,
                stmt.legend && `Условие:\n${stmt.legend}`,
                stmt.input && `Входные данные:\n${stmt.input}`,
                stmt.output && `Выходные данные:\n${stmt.output}`,
                stmt.notes && `Примечания:\n${stmt.notes}`,
                stmt.tutorial && `Разбор:\n${stmt.tutorial}`,
            ].filter(Boolean).join('\n\n');
            setAttachments(prev => [...prev, { id: key, label: 'Условие задачи', content, icon: 'statement' }]);
        } catch {
            //
        } finally {
            setLoadingAttach(null);
        }
    };

    const removeAttachment = (id: string) => {
        setAttachments(prev => prev.filter(a => a.id !== id));
    };

    const sendMessage = async () => {
        const text = input.trim();
        if (!text || sending || !sessionId) return;

        const userMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'user',
            content: text,
            timestamp: new Date().toISOString(),
        };

        setMessages(prev => [...prev, userMsg]);
        setInput('');
        const currentAttachments = [...attachments];
        setAttachments([]);
        setSending(true);
        setPickerMode(null);

        try {
            const res = await api.post('/ai/polygon-chat', {
                session_id: sessionId,
                message: text,
                model: model,
                attachments: currentAttachments.map(a => ({
                    type: a.icon,
                    label: a.label,
                    content: a.content,
                })),
            });

            const assistantMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: res.data.response || res.data.message || '',
                timestamp: new Date().toISOString(),
            };
            setMessages(prev => [...prev, assistantMsg]);
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

    const AttachIcon = ({ icon }: { icon: Attachment['icon'] }) => {
        if (icon === 'file') return <FileText size={10} />;
        if (icon === 'test') return <TestTube size={10} />;
        return <BookOpen size={10} />;
    };

    return (
        <div className="w-80 shrink-0 flex flex-col border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 relative">
            {/* Header */}
            <div className="shrink-0 px-3 py-2 border-b border-slate-100 dark:border-slate-800 flex items-center gap-2">
                <Bot size={15} className="text-blue-500 shrink-0" />
                <span className="text-xs font-bold text-slate-700 dark:text-slate-200 flex-1">AI Агент</span>
                <div className="relative">
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

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-slate-400 text-center py-8">
                        <Bot size={32} className="mb-2 opacity-20" />
                        <p className="text-xs font-bold">AI Агент</p>
                        <p className="text-[10px] mt-1 opacity-70">
                            Агент сам запрашивает нужные данные задачи.<br/>
                            Можно прикрепить файл или тест как контекст.
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
                                    ${msg.role === 'system'
                                        ? 'bg-slate-100 dark:bg-slate-800'
                                        : 'bg-blue-100 dark:bg-blue-900/40'}`}>
                                    <Bot size={12} className={msg.role === 'system' ? 'text-slate-400' : 'text-blue-500'} />
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
                                    : msg.role === 'system'
                                        ? 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 italic'
                                        : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200'
                                }`}>
                                <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                                <p className={`text-[9px] mt-1 opacity-60 ${msg.role === 'user' ? 'text-right' : ''}`}>
                                    {formatTime(msg.timestamp)}
                                </p>
                            </div>
                        </div>
                    ))
                )}
                {sending && (
                    <div className="flex gap-2">
                        <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center shrink-0">
                            <Bot size={12} className="text-blue-500" />
                        </div>
                        <div className="bg-slate-100 dark:bg-slate-800 rounded-2xl px-3 py-2 flex items-center gap-2">
                            <Loader2 size={12} className="animate-spin text-slate-400" />
                            <span className="text-[10px] text-slate-400">Думает...</span>
                        </div>
                    </div>
                )}
                <div ref={bottomRef} />
            </div>

            {/* Picker dropdown */}
            {pickerMode && (
                <div className="absolute bottom-[130px] left-2 right-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl z-10 max-h-48 overflow-y-auto">
                    {pickerLoading ? (
                        <div className="flex items-center justify-center py-4">
                            <Loader2 size={16} className="animate-spin text-blue-500" />
                        </div>
                    ) : pickerMode === 'files' ? (
                        files.length === 0 ? (
                            <p className="text-xs text-slate-400 p-3 italic">Нет файлов</p>
                        ) : (
                            files.map(f => (
                                <button
                                    key={`${f.section}-${f.name}`}
                                    onClick={() => attachFile(f)}
                                    disabled={loadingAttach === `file-${f.section}-${f.name}`}
                                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-slate-700 dark:text-slate-200
                                               hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors text-left disabled:opacity-50"
                                >
                                    <FileText size={12} className="text-slate-400 shrink-0" />
                                    <span className="flex-1 truncate font-mono">{f.name}</span>
                                    <span className="text-[10px] text-slate-400 shrink-0">{f.section}</span>
                                    {loadingAttach === `file-${f.section}-${f.name}` && (
                                        <Loader2 size={10} className="animate-spin text-blue-500 shrink-0" />
                                    )}
                                </button>
                            ))
                        )
                    ) : (
                        tests.length === 0 ? (
                            <p className="text-xs text-slate-400 p-3 italic">Нет тестов</p>
                        ) : (
                            tests.map(t => (
                                <button
                                    key={t.index}
                                    onClick={() => attachTest(t)}
                                    disabled={loadingAttach === `test-${t.index}`}
                                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-slate-700 dark:text-slate-200
                                               hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors text-left disabled:opacity-50"
                                >
                                    <TestTube size={12} className="text-slate-400 shrink-0" />
                                    <span className="font-bold shrink-0">#{t.index}</span>
                                    {t.preview && (
                                        <span className="flex-1 truncate text-slate-400 font-mono">{t.preview}</span>
                                    )}
                                    {loadingAttach === `test-${t.index}` && (
                                        <Loader2 size={10} className="animate-spin text-blue-500 shrink-0" />
                                    )}
                                </button>
                            ))
                        )
                    )}
                </div>
            )}

            {/* Attachments chips */}
            {attachments.length > 0 && (
                <div className="shrink-0 px-2 pt-1.5 flex flex-wrap gap-1">
                    {attachments.map(a => (
                        <div
                            key={a.id}
                            className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold
                                       bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
                        >
                            <AttachIcon icon={a.icon} />
                            <span className="max-w-[80px] truncate">{a.label}</span>
                            <button
                                onClick={() => removeAttachment(a.id)}
                                className="ml-0.5 hover:text-blue-800 dark:hover:text-blue-200"
                            >
                                <X size={9} />
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {/* Input area */}
            <div className="shrink-0 border-t border-slate-100 dark:border-slate-800 p-2 space-y-1.5">
                {/* Attach buttons */}
                <div className="flex gap-1">
                    <button
                        onClick={attachStatement}
                        disabled={loadingAttach === 'statement-russian'}
                        className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold
                                   bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-blue-500
                                   hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all disabled:opacity-50"
                    >
                        {loadingAttach === 'statement-russian'
                            ? <Loader2 size={10} className="animate-spin" />
                            : <BookOpen size={10} />
                        }
                        Условие
                    </button>
                    <button
                        onClick={openFilePicker}
                        className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold transition-all
                                   ${pickerMode === 'files'
                                       ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                                       : 'bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20'
                                   }`}
                    >
                        <FileText size={10} />
                        Файл
                    </button>
                    <button
                        onClick={openTestsPicker}
                        className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold transition-all
                                   ${pickerMode === 'tests'
                                       ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                                       : 'bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20'
                                   }`}
                    >
                        <TestTube size={10} />
                        Тест
                    </button>
                </div>

                <div className="flex gap-2 items-end">
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={sessionId ? 'Сообщение... (Enter)' : 'Нет активной сессии'}
                        disabled={!sessionId || sending}
                        rows={2}
                        className="flex-1 resize-none text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700
                                   rounded-xl px-3 py-2 outline-none dark:text-white placeholder:text-slate-400
                                   focus:border-blue-500 transition-all disabled:opacity-50 min-h-[52px] max-h-32"
                    />
                    <button
                        onClick={sendMessage}
                        disabled={!input.trim() || sending || !sessionId}
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
