import { useState, useEffect, useRef } from 'react';
import {
    Send, Sparkles, Loader2, CheckCircle, AlertCircle,
    FileText, UploadCloud, RotateCcw
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { api } from '../api/instance';

// Типы данных
interface Statement {
    name: string;
    legend: string;
    input: string;
    output: string;
    notes?: string;
    tutorial?: string;
}

interface Progress {
    status: 'uploading' | 'done' | 'failed' | 'idle';
    current_step?: string;
    error?: string;
    retries?: number;
}

export const AITasks = () => {
    // Состояние диалога
    const [messages, setMessages] = useState<{role: 'user' | 'assistant', content: string}[]>([]);
    const [inputValue, setInputValue] = useState('');
    const [loading, setLoading] = useState(false);

    // Состояние задачи
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [statement, setStatement] = useState<Statement | null>(null);
    const [problemId, setProblemId] = useState<string>(''); // ID задачи в Polygon

    // Состояние прогресса выгрузки
    const [progress, setProgress] = useState<Progress>({ status: 'idle' });
    const chatEndRef = useRef<HTMLDivElement>(null);

    // Скролл чата вниз
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // 1. Отправка сообщения (Первая генерация или уточнение)
    const handleSendMessage = async () => {
        if (!inputValue.trim()) return;

        const userMessage = inputValue;
        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
        setInputValue('');
        setLoading(true);

        try {
            if (!sessionId) {
                // Первая генерация
                const res = await api.post('/ai/generate-statement', {
                    idea: userMessage,
                    history: []
                });
                setStatement(res.data.statement);
                setSessionId(res.data.session_id);
                setMessages(prev => [...prev, { role: 'assistant', content: "Я подготовил черновик условия. Что-нибудь исправим или добавим?" }]);
            } else {
                // Уточнение
                const res = await api.post('/ai/refine-statement', {
                    session_id: sessionId,
                    feedback: userMessage
                });
                setStatement(res.data.statement);
                setMessages(prev => [...prev, { role: 'assistant', content: "Обновил условие в соответствии с вашими правками." }]);
            }
        } catch (e: any) {
            setMessages(prev => [...prev, { role: 'assistant', content: "Произошла ошибка при связи с ИИ. Попробуйте еще раз." }]);
        } finally {
            setLoading(false);
        }
    };

    // 2. Утверждение и запуск выгрузки в Polygon
    const handleApproveAndUpload = async () => {
        if (!problemId) {
            alert("Пожалуйста, введите Problem ID из Polygon");
            return;
        }

        try {
            setProgress({ status: 'uploading', current_step: 'Инициализация...' });
            await api.post('/ai/approve-and-upload', {
                session_id: sessionId,
                problem_id: parseInt(problemId),
                user_id: 1 // В реальности берем из стора
            });
            startPollingProgress();
        } catch (e) {
            setProgress({ status: 'failed', error: 'Не удалось запустить процесс выгрузки' });
        }
    };

    // 3. Опрос прогресса (Polling)
    const startPollingProgress = () => {
        const interval = setInterval(async () => {
            try {
                const res = await api.get(`/ai/upload-progress/${sessionId}`);
                const data = res.data;
                setProgress(data);

                if (data.status === 'done' || data.status === 'failed') {
                    clearInterval(interval);
                }
            } catch (e) {
                console.error("Polling error", e);
            }
        }, 2000);
    };

    return (
        <div className="flex h-[calc(100vh-120px)] gap-6 animate-in fade-in duration-500">

            {/* ЛЕВАЯ ЧАСТЬ: Предпросмотр условия */}
            <div className="flex-1 bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden shadow-sm">
                <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-800/50">
                    <div className="flex items-center gap-2 font-bold dark:text-white text-slate-700">
                        <FileText size={18} className="text-blue-500" />
                        Предпросмотр задачи
                    </div>
                    {statement && (
                        <div className="flex items-center gap-3">
                            <input
                                type="number"
                                placeholder="Polygon ID"
                                className="w-24 px-3 py-1 text-sm rounded-lg border dark:bg-slate-800 dark:border-slate-700 dark:text-white outline-none focus:ring-2 focus:ring-blue-500"
                                value={problemId}
                                onChange={(e) => setProblemId(e.target.value)}
                            />
                            <button
                                onClick={handleApproveAndUpload}
                                disabled={progress.status === 'uploading'}
                                className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-1.5 rounded-xl text-sm font-bold transition-all disabled:opacity-50"
                            >
                                <UploadCloud size={16} />
                                {progress.status === 'uploading' ? 'Выгрузка...' : 'В Polygon'}
                            </button>
                        </div>
                    )}
                </div>

                <div className="flex-1 overflow-y-auto p-8 prose dark:prose-invert max-w-none">
                    {statement ? (
                        <div className="space-y-6">
                            <h1 className="text-3xl font-extrabold text-center mb-8">{statement.name}</h1>

                            <section>
                                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                    {statement.legend}
                                </ReactMarkdown>
                            </section>

                            <div>
                                <h3 className="text-lg font-bold border-b pb-1 mb-2">Входные данные</h3>
                                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                    {statement.input}
                                </ReactMarkdown>
                            </div>

                            <div>
                                <h3 className="text-lg font-bold border-b pb-1 mb-2">Выходные данные</h3>
                                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                    {statement.output}
                                </ReactMarkdown>
                            </div>

                            {statement.notes && (
                                <div className="bg-slate-50 dark:bg-slate-800/50 p-4 rounded-2xl">
                                    <h3 className="text-sm font-bold uppercase text-slate-400 mb-2">Примечание</h3>
                                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                        {statement.notes}
                                    </ReactMarkdown>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-4">
                            <Sparkles size={48} className="opacity-20 animate-pulse" />
                            <p className="text-center max-w-xs">Опишите идею задачи в чате справа, чтобы ИИ составил условие</p>
                        </div>
                    )}
                </div>
            </div>

            {/* ПРАВАЯ ЧАСТЬ: Чат с ИИ */}
            <div className="w-[400px] flex flex-col gap-4">

                {/* Окно сообщений */}
                <div className="flex-1 bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden shadow-sm">
                    <div className="p-4 border-b border-slate-100 dark:border-slate-800 font-bold dark:text-white flex items-center gap-2">
                        <Sparkles size={18} className="text-indigo-500" />
                        AI Помощник
                    </div>

                    <div className="flex-1 overflow-y-auto p-4 space-y-4">
                        {messages.length === 0 && (
                            <div className="text-xs text-slate-400 text-center mt-10">
                                Отправьте идею, например: <br/>
                                <span className="italic">"Задача про массив, где нужно найти сумму четных чисел на отрезке"</span>
                            </div>
                        )}
                        {messages.map((m, i) => (
                            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[85%] px-4 py-2 rounded-2xl text-sm ${
                                    m.role === 'user'
                                        ? 'bg-blue-600 text-white rounded-tr-none'
                                        : 'bg-slate-100 dark:bg-slate-800 dark:text-white rounded-tl-none'
                                }`}>
                                    {m.content}
                                </div>
                            </div>
                        ))}
                        {loading && (
                            <div className="flex justify-start">
                                <div className="bg-slate-100 dark:bg-slate-800 p-3 rounded-2xl rounded-tl-none">
                                    <Loader2 size={16} className="animate-spin text-blue-500" />
                                </div>
                            </div>
                        )}
                        <div ref={chatEndRef} />
                    </div>

                    <div className="p-4 bg-slate-50 dark:bg-slate-800/50">
                        <div className="relative">
                            <textarea
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSendMessage())}
                                placeholder="Опишите задачу или правки..."
                                className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl p-3 pr-12 text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:text-white resize-none h-24"
                            />
                            <button
                                onClick={handleSendMessage}
                                disabled={loading || !inputValue.trim()}
                                className="absolute right-3 bottom-3 p-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-colors"
                            >
                                <Send size={18} />
                            </button>
                        </div>
                    </div>
                </div>

                {/* Статус выгрузки (Progress Card) */}
                {progress.status !== 'idle' && (
                    <div className="bg-white dark:bg-slate-900 p-5 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-lg animate-in slide-in-from-bottom-4">
                        <div className="flex items-center justify-between mb-4">
                            <span className="font-bold text-sm dark:text-white">Статус выгрузки</span>
                            {progress.status === 'uploading' && <Loader2 size={16} className="animate-spin text-blue-500" />}
                            {progress.status === 'done' && <CheckCircle size={16} className="text-green-500" />}
                            {progress.status === 'failed' && <AlertCircle size={16} className="text-red-500" />}
                        </div>

                        <div className="space-y-3">
                            <div className="flex items-center gap-3 text-xs">
                                <div className={`w-2 h-2 rounded-full ${progress.status === 'done' ? 'bg-green-500' : 'bg-blue-500 animate-pulse'}`}></div>
                                <span className="text-slate-500 dark:text-slate-400">
                                    Шаг: <span className="font-bold text-slate-700 dark:text-slate-200">{progress.current_step || 'Завершено'}</span>
                                </span>
                            </div>

                            {progress.retries && parseInt(String(progress.retries)) > 0 && (
                                <div className="text-[10px] bg-amber-50 dark:bg-amber-900/20 text-amber-600 px-2 py-1 rounded-md flex items-center gap-1">
                                    <RotateCcw size={10} /> Попытка исправления #{progress.retries}
                                </div>
                            )}

                            {progress.error && (
                                <div className="text-[10px] text-red-500 bg-red-50 dark:bg-red-900/20 p-2 rounded-lg break-words">
                                    {progress.error}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
