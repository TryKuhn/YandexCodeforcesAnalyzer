// pages/AITasksList.tsx

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Plus, Sparkles, Loader2, Trash2, ExternalLink,
    FileText, Code, UploadCloud, Package, CheckCircle,
    AlertCircle, Clock, ChevronRight, Download, X
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
    const [deletingId, setDeletingId] = useState<string | null>(null);

    const [showImportDialog, setShowImportDialog] = useState(false);
    const [importProblemId, setImportProblemId] = useState('');
    const [importLoadFiles, setImportLoadFiles] = useState(true);
    const [importing, setImporting] = useState(false);
    const [importError, setImportError] = useState<string | null>(null);

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

    const handleCreate = async () => {
        if (creating) return;
        setCreating(true);
        try {
            const settings = loadSettings();
            const res = await api.post('/ai/create-session', {
                idea: '',
                model: settings.model,
                user_prompt: settings.systemPrompt,
            });
            navigate(`/ai-tasks/${res.data.session_id}`);
        } catch (e) {
            console.error('Failed to create session', e);
        } finally {
            setCreating(false);
        }
    };

    const handleImport = async () => {
        const id = parseInt(importProblemId.trim(), 10);
        if (!id || isNaN(id)) { setImportError('Введите корректный ID задачи'); return; }
        setImporting(true);
        setImportError(null);
        try {
            const settings = loadSettings();
            const res = await api.post('/ai/import-from-polygon-full', {
                polygon_problem_id: id,
                model: settings.model,
                load_files: importLoadFiles,
            });
            navigate(`/ai-tasks/${res.data.session_id}`);
        } catch (e: any) {
            setImportError(e?.response?.data?.detail || 'Ошибка импорта. Проверьте ID и настройки Polygon.');
        } finally {
            setImporting(false);
        }
    };

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
        <>
        <div className="max-w-4xl mx-auto py-4 sm:py-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 sm:mb-8">
                    <div>
                        <h1 className="text-2xl sm:text-3xl font-black text-slate-800 dark:text-white flex items-center gap-3">
                            <Sparkles className="text-blue-500" size={28} />
                            AI Задачи
                        </h1>
                        <p className="text-slate-500 mt-1 text-sm">
                            Создавайте задачи для Polygon с помощью ИИ
                        </p>
                    </div>

                    <div className="flex gap-2 shrink-0">
                        <button
                            onClick={() => { setShowImportDialog(true); setImportError(null); setImportProblemId(''); }}
                            className="flex items-center gap-2 bg-slate-100 dark:bg-slate-800
                                       hover:bg-slate-200 dark:hover:bg-slate-700
                                       text-slate-700 dark:text-slate-300 px-4 py-2.5 sm:px-5 sm:py-3 rounded-2xl font-bold text-sm
                                       transition-all active:scale-95"
                        >
                            <Download size={16} />
                            <span className="hidden sm:inline">Из Polygon</span>
                            <span className="sm:hidden">Polygon</span>
                        </button>
                        <button
                            onClick={handleCreate}
                            disabled={creating}
                            className="flex items-center gap-2 bg-gradient-to-r from-violet-600 to-fuchsia-600
                                       hover:from-violet-700 hover:to-fuchsia-700
                                       text-white px-4 py-2.5 sm:px-6 sm:py-3 rounded-2xl font-bold text-sm
                                       transition-all shadow-lg shadow-violet-500/20
                                       hover:shadow-xl hover:shadow-violet-500/30
                                       active:scale-95 disabled:opacity-60"
                        >
                            {creating
                                ? <Loader2 size={18} className="animate-spin" />
                                : <Plus size={18} />
                            }
                            Новая задача
                        </button>
                    </div>
                </div>

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
                                            <h3 className="font-bold text-slate-800
                                                           dark:text-white text-lg truncate
                                                           group-hover:text-blue-600
                                                           dark:group-hover:text-blue-400
                                                           transition-colors">
                                                {session.name}
                                            </h3>

                                            <div className="flex items-center gap-3 mt-2
                                                            flex-wrap">
                                                <span className={`
                                                    flex items-center gap-1.5 px-2.5 py-1
                                                    rounded-full text-[11px] font-bold
                                                    ${stageConf.color} ${stageConf.bg}
                                                `}>
                                                    {stageConf.icon}
                                                    {stageConf.label}
                                                </span>

                                                <span className="hidden sm:inline-flex text-[11px] text-slate-400
                                                                 bg-slate-100
                                                                 dark:bg-slate-800
                                                                 px-2 py-1 rounded-full
                                                                 font-mono max-w-[120px] truncate">
                                                    {session.model.split('/').pop()}
                                                </span>

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

        {showImportDialog && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 sm:p-8 w-full max-w-md shadow-2xl mx-4">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-xl font-black dark:text-white flex items-center gap-2">
                            <Download size={20} className="text-blue-500" />
                            Импорт из Polygon
                        </h2>
                        <button onClick={() => setShowImportDialog(false)} className="p-2 text-slate-400 hover:text-slate-700 dark:hover:text-white rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-all">
                            <X size={18} />
                        </button>
                    </div>
                    <p className="text-sm text-slate-500 mb-4">
                        Введите ID задачи из Polygon. Условие, файлы, теги и настройки будут импортированы.
                    </p>
                    <input
                        type="number"
                        value={importProblemId}
                        onChange={e => setImportProblemId(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') handleImport(); }}
                        placeholder="ID задачи (например, 12345)"
                        className="w-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 rounded-2xl px-4 py-3 text-sm dark:text-white outline-none focus:border-blue-500 transition-all mb-3"
                        autoFocus
                    />
                    <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-3 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={importLoadFiles}
                            onChange={e => setImportLoadFiles(e.target.checked)}
                            className="rounded"
                        />
                        Загрузить файлы (решения, валидатор, чекер, скрипт)
                    </label>
                    {importError && (
                        <p className="text-sm text-red-500 mb-3">{importError}</p>
                    )}
                    <button
                        onClick={handleImport}
                        disabled={importing || !importProblemId.trim()}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                    >
                        {importing ? <Loader2 size={18} className="animate-spin" /> : <Download size={18} />}
                        Импортировать
                    </button>
                </div>
            </div>
        )}
        </>
    );
};
