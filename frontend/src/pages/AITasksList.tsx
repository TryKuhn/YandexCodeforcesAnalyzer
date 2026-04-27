// pages/AITasksList.tsx

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Plus, Sparkles, Loader2, Trash2, ExternalLink,
    FileText, Code, UploadCloud, Package, CheckCircle,
    AlertCircle, Clock, ChevronRight
} from 'lucide-react';
import { api } from '../api/instance';
import { useAISettings } from '../components/layout/MainLayout';

interface SessionSummary {
    session_id: string;
    stage: string;
    name: string;
    model: string;
    polygon_problem_id: number | null;
    created_at: string | null;
    updated_at: string | null;
}

const STAGE_CONFIG: Record<string, {
    label: string;
    icon: React.ReactNode;
    color: string;
    bg: string;
}> = {
    statement: {
        label: 'Условие',
        icon: <FileText size={14} />,
        color: 'text-blue-600 dark:text-blue-400',
        bg: 'bg-blue-50 dark:bg-blue-900/20',
    },
    files_review: {
        label: 'Проверка файлов',
        icon: <Code size={14} />,
        color: 'text-purple-600 dark:text-purple-400',
        bg: 'bg-purple-50 dark:bg-purple-900/20',
    },
    uploading: {
        label: 'Загрузка',
        icon: <UploadCloud size={14} />,
        color: 'text-amber-600 dark:text-amber-400',
        bg: 'bg-amber-50 dark:bg-amber-900/20',
    },
    fixing_errors: {
        label: 'Исправление ошибок',
        icon: <AlertCircle size={14} />,
        color: 'text-red-600 dark:text-red-400',
        bg: 'bg-red-50 dark:bg-red-900/20',
    },
    building_package: {
        label: 'Сборка пакета',
        icon: <Package size={14} />,
        color: 'text-orange-600 dark:text-orange-400',
        bg: 'bg-orange-50 dark:bg-orange-900/20',
    },
    done: {
        label: 'Готово',
        icon: <CheckCircle size={14} />,
        color: 'text-green-600 dark:text-green-400',
        bg: 'bg-green-50 dark:bg-green-900/20',
    },
    failed: {
        label: 'Ошибка',
        icon: <AlertCircle size={14} />,
        color: 'text-red-600 dark:text-red-400',
        bg: 'bg-red-50 dark:bg-red-900/20',
    },
};

export const AITasksList = () => {
    const navigate = useNavigate();
    const { load: loadSettings } = useAISettings();

    const [sessions, setSessions] = useState<SessionSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [creating, setCreating] = useState(false);
    const [newTaskIdea, setNewTaskIdea] = useState('');
    const [showNewForm, setShowNewForm] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);

    // Загрузка списка сессий
    const fetchSessions = async () => {
        try {
            setLoading(true);
            const res = await api.get('/ai/sessions');
            setSessions(res.data);
        } catch (e) {
            console.error('Failed to load sessions', e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSessions();
    }, []);

    // Создание новой сессии
    const handleCreate = async () => {
        if (!newTaskIdea.trim() || creating) return;

        setCreating(true);
        try {
            const settings = loadSettings();
            const res = await api.post('/ai/create-session', {
                idea: newTaskIdea.trim(),
                model: settings.model,
                user_prompt: settings.systemPrompt,
                history: [],
            });
            navigate(`/ai-tasks/${res.data.session_id}`);
        } catch (e) {
            console.error('Failed to create session', e);
        } finally {
            setCreating(false);
        }
    };

    // Удаление сессии
    const handleDelete = async (sessionId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm('Удалить эту сессию?')) return;

        setDeletingId(sessionId);
        try {
            await api.delete(`/ai/session/${sessionId}`);
            setSessions(prev => prev.filter(s => s.session_id !== sessionId));
        } catch (err) {
            console.error('Failed to delete session', err);
        } finally {
            setDeletingId(null);
        }
    };

    // Форматирование даты
    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now.getTime() - date.getTime();

        if (diff < 60000) return 'только что';
        if (diff < 3600000) return `${Math.floor(diff / 60000)} мин назад`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)} ч назад`;

        return date.toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    return (
        <div className="min-h-[calc(100vh-80px)] bg-slate-50 dark:bg-slate-950 p-6">
            <div className="max-w-4xl mx-auto">

                {/* Заголовок */}
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-3xl font-black text-slate-800 dark:text-white flex items-center gap-3">
                            <Sparkles className="text-blue-500" size={32} />
                            AI Задачи
                        </h1>
                        <p className="text-slate-500 mt-1 text-sm">
                            Создавайте задачи для Polygon с помощью ИИ
                        </p>
                    </div>

                    <button
                        onClick={() => setShowNewForm(true)}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700
                                   text-white px-6 py-3 rounded-2xl font-bold
                                   transition-all shadow-lg shadow-blue-500/20
                                   hover:shadow-xl hover:shadow-blue-500/30
                                   active:scale-95"
                    >
                        <Plus size={20} />
                        Новая задача
                    </button>
                </div>

                {/* Форма создания новой задачи */}
                {showNewForm && (
                    <div className="mb-6 bg-white dark:bg-slate-900 rounded-2xl border-2
                                    border-blue-200 dark:border-blue-800 p-6 shadow-xl
                                    animate-in slide-in-from-top-4 duration-300">
                        <h3 className="font-bold text-sm text-slate-700 dark:text-slate-200 mb-3">
                            Опишите идею задачи
                        </h3>
                        <textarea
                            value={newTaskIdea}
                            onChange={e => setNewTaskIdea(e.target.value)}
                            onKeyDown={e => {
                                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                                    handleCreate();
                                }
                            }}
                            placeholder="Например: задача на бинарный поиск по ответу, где нужно распределить задания между работниками..."
                            className="w-full bg-slate-50 dark:bg-slate-800 border-2
                                       border-transparent focus:border-blue-500
                                       rounded-xl p-4 text-sm outline-none dark:text-white
                                       transition-all resize-none h-28"
                            autoFocus
                        />
                        <div className="flex justify-end gap-2 mt-3">
                            <button
                                onClick={() => {
                                    setShowNewForm(false);
                                    setNewTaskIdea('');
                                }}
                                className="px-4 py-2 text-sm text-slate-500
                                           hover:text-slate-700 dark:hover:text-slate-300
                                           rounded-xl transition-all"
                            >
                                Отмена
                            </button>
                            <button
                                onClick={handleCreate}
                                disabled={!newTaskIdea.trim() || creating}
                                className="flex items-center gap-2 bg-blue-600
                                           hover:bg-blue-700 text-white px-5 py-2
                                           rounded-xl font-bold text-sm transition-all
                                           disabled:opacity-50 shadow-lg"
                            >
                                {creating ? (
                                    <Loader2 size={16} className="animate-spin" />
                                ) : (
                                    <Sparkles size={16} />
                                )}
                                Создать
                            </button>
                        </div>
                        <p className="text-[10px] text-slate-400 mt-2">
                            Ctrl+Enter для быстрой отправки
                        </p>
                    </div>
                )}

                {/* Список сессий */}
                {loading ? (
                    <div className="flex flex-col items-center justify-center py-20">
                        <Loader2 size={32} className="animate-spin text-blue-500 mb-4" />
                        <p className="text-slate-400 text-sm">Загрузка сессий...</p>
                    </div>
                ) : sessions.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20
                                    text-slate-400">
                        <Sparkles size={64} className="mb-4 opacity-10" />
                        <p className="font-bold text-lg">Пока нет задач</p>
                        <p className="text-sm mt-2">
                            Нажмите «Новая задача», чтобы начать
                        </p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {sessions.map(session => {
                            const stageConf = STAGE_CONFIG[session.stage]
                                || STAGE_CONFIG.statement;

                            return (
                                <div
                                    key={session.session_id}
                                    onClick={() =>
                                        navigate(`/ai-tasks/${session.session_id}`)
                                    }
                                    className="group bg-white dark:bg-slate-900 rounded-2xl
                                               border border-slate-200 dark:border-slate-800
                                               p-5 cursor-pointer transition-all
                                               hover:border-blue-300 dark:hover:border-blue-700
                                               hover:shadow-lg hover:shadow-blue-500/5
                                               active:scale-[0.99]"
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex-1 min-w-0">
                                            {/* Название задачи */}
                                            <h3 className="font-bold text-slate-800
                                                           dark:text-white text-lg truncate
                                                           group-hover:text-blue-600
                                                           dark:group-hover:text-blue-400
                                                           transition-colors">
                                                {session.name}
                                            </h3>

                                            {/* Мета-информация */}
                                            <div className="flex items-center gap-3 mt-2
                                                            flex-wrap">
                                                {/* Стадия */}
                                                <span className={`
                                                    flex items-center gap-1.5 px-2.5 py-1
                                                    rounded-full text-[11px] font-bold
                                                    ${stageConf.color} ${stageConf.bg}
                                                `}>
                                                    {stageConf.icon}
                                                    {stageConf.label}
                                                </span>

                                                {/* Модель */}
                                                <span className="text-[11px] text-slate-400
                                                                 bg-slate-100
                                                                 dark:bg-slate-800
                                                                 px-2 py-1 rounded-full
                                                                 font-mono">
                                                    {session.model}
                                                </span>

                                                {/* Polygon ID */}
                                                {session.polygon_problem_id && (
                                                    <a
                                                        href={`https://polygon.codeforces.com/problems/${session.polygon_problem_id}`}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        onClick={e => e.stopPropagation()}
                                                        className="flex items-center gap-1
                                                                   text-[11px] text-green-600
                                                                   dark:text-green-400
                                                                   bg-green-50
                                                                   dark:bg-green-900/20
                                                                   px-2 py-1 rounded-full
                                                                   font-bold
                                                                   hover:bg-green-100
                                                                   dark:hover:bg-green-900/40
                                                                   transition-colors"
                                                    >
                                                        <ExternalLink size={10} />
                                                        Polygon #{session.polygon_problem_id}
                                                    </a>
                                                )}

                                                {/* Время */}
                                                <span className="flex items-center gap-1
                                                                 text-[11px] text-slate-400">
                                                    <Clock size={10} />
                                                    {formatDate(
                                                        session.updated_at
                                                        || session.created_at
                                                    )}
                                                </span>
                                            </div>
                                        </div>

                                        {/* Правая часть: кнопки */}
                                        <div className="flex items-center gap-2 ml-4">
                                            <button
                                                onClick={e => handleDelete(
                                                    session.session_id, e
                                                )}
                                                disabled={deletingId === session.session_id}
                                                className="p-2 text-slate-400
                                                           hover:text-red-500
                                                           hover:bg-red-50
                                                           dark:hover:bg-red-900/20
                                                           rounded-xl transition-all
                                                           opacity-0
                                                           group-hover:opacity-100"
                                            >
                                                {deletingId === session.session_id ? (
                                                    <Loader2
                                                        size={16}
                                                        className="animate-spin"
                                                    />
                                                ) : (
                                                    <Trash2 size={16} />
                                                )}
                                            </button>
                                            <ChevronRight
                                                size={20}
                                                className="text-slate-300
                                                           dark:text-slate-700
                                                           group-hover:text-blue-500
                                                           transition-colors"
                                            />
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};
