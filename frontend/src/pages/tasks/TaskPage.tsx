// pages/tasks/TaskPage.tsx

import { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2, AlertCircle, FileText, Folder, TestTube, Package } from 'lucide-react';
import { api } from '../../api/instance';
import { ProblemHeader } from './components/ProblemHeader';
import { ChatPanel } from './components/ChatPanel';
import { StatementTab } from './tabs/StatementTab';
import { FilesTab } from './tabs/FilesTab';
import { TestsTab } from './tabs/TestsTab';
import { PackagesTab } from './tabs/PackagesTab';

// ─── Types ───────────────────────────────────────────────────────────────────

interface PolygonProblem {
    id: number;
    polygon_id: number;
    name: string;
    owner: string;
    access_type: string | null;
    revision: number | null;
    modified: boolean;
    deleted: boolean;
    interactive: boolean;
    enable_groups: boolean;
    list_fetched_at: string | null;
    info_fetched_at: string | null;
}

interface SessionData {
    session_id: string;
    model: string;
    problem_type?: string;
    chat_log: ChatMessage[];
    problem_settings?: Record<string, unknown>;
    stage?: string;
    [key: string]: unknown;
}

interface ChatMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: string;
}

type TabId = 'statement' | 'files' | 'tests' | 'packages';

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: 'statement', label: 'Условие',  icon: <FileText size={14} /> },
    { id: 'files',     label: 'Файлы',    icon: <Folder size={14} /> },
    { id: 'tests',     label: 'Тесты',    icon: <TestTube size={14} /> },
    { id: 'packages',  label: 'Пакеты',   icon: <Package size={14} /> },
];

const DEFAULT_MODEL = 'anthropic/claude-sonnet-4.6';

// Chat panel resize bounds
const CHAT_MIN_W = 280;
const CHAT_DEFAULT_W = 320;
const CHAT_WIDTH_KEY = 'taskChatPanelWidth';

// ─── Component ───────────────────────────────────────────────────────────────

export const TaskPage = () => {
    const { polygonId: polygonIdStr } = useParams<{ polygonId: string }>();
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const polygonId = Number(polygonIdStr);

    const initialTab = TABS.some(t => t.id === searchParams.get('tab'))
        ? (searchParams.get('tab') as TabId)
        : 'statement';

    // Persist the active tab in the URL so a page reload stays on it.
    const changeTab = (tab: TabId) => {
        setActiveTab(tab);
        setSearchParams(prev => {
            const next = new URLSearchParams(prev);
            next.set('tab', tab);
            return next;
        }, { replace: true });
    };

    const [problem, setProblem] = useState<PolygonProblem | null>(null);
    const [session, setSession] = useState<SessionData | null>(null);
    const [activeTab, setActiveTab] = useState<TabId>(initialTab);

    // Resizable chat panel width (persisted)
    const [chatWidth, setChatWidth] = useState(() => {
        const saved = Number(localStorage.getItem(CHAT_WIDTH_KEY));
        return saved >= CHAT_MIN_W ? saved : CHAT_DEFAULT_W;
    });

    const startChatResize = (e: React.MouseEvent) => {
        e.preventDefault();
        const maxW = Math.floor(window.innerWidth * 0.7);
        const onMove = (ev: MouseEvent) => {
            setChatWidth(Math.min(Math.max(window.innerWidth - ev.clientX, CHAT_MIN_W), maxW));
        };
        const onUp = () => {
            window.removeEventListener('mousemove', onMove);
            window.removeEventListener('mouseup', onUp);
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            setChatWidth(w => { localStorage.setItem(CHAT_WIDTH_KEY, String(w)); return w; });
        };
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
    };
    const [chatModel, setChatModel] = useState(DEFAULT_MODEL);
    const [problemType, setProblemType] = useState('regular');
    const [savingType, setSavingType] = useState(false);
    const [reloadKey, setReloadKey] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const handleModelChange = async (newModel: string) => {
        setChatModel(newModel);
        if (!session?.session_id) return;
        try {
            await api.patch(`/ai/session/${session.session_id}/settings`, { model: newModel });
        } catch {
            // keep local selection even if persistence fails
        }
    };

    const handleProblemTypeChange = async (newType: string) => {
        if (!session?.session_id || newType === problemType) return;
        const prev = problemType;
        setProblemType(newType);
        setSavingType(true);
        try {
            await api.patch(`/ai/session/${session.session_id}/problem-type`, {
                problem_type: newType,
            });
        } catch {
            setProblemType(prev);
        } finally {
            setSavingType(false);
        }
    };

    useEffect(() => {
        if (!polygonId) return;
        loadAll();
    }, [polygonId]);

    const loadAll = async () => {
        setLoading(true);
        setError(null);
        try {
            const [sessionRes, problemRes] = await Promise.allSettled([
                api.get(`/polygon/problems/${polygonId}/session`),
                api.get(`/polygon/problems/${polygonId}`),
            ]);

            if (sessionRes.status === 'fulfilled') {
                const s: SessionData = sessionRes.value.data;
                setSession(s);
                if (s.model) setChatModel(s.model);
                if (s.problem_type) setProblemType(s.problem_type);
                // Auto-pull the current Polygon state into the AI session in the
                // background, then refresh the tabs once it lands.
                if (s.session_id) {
                    api.post(`/ai/session/${s.session_id}/sync-from-polygon`)
                        .then(() => setReloadKey(k => k + 1))
                        .catch(() => { /* non-fatal */ });
                }
            }

            if (problemRes.status === 'fulfilled') {
                setProblem(problemRes.value.data as PolygonProblem);
            } else if (problemRes.status === 'rejected') {
                const err = (problemRes.reason as any);
                setError(err?.response?.data?.detail || 'Ошибка загрузки задачи');
            }
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full bg-slate-50 dark:bg-slate-950">
                <div className="text-center">
                    <Loader2 size={36} className="animate-spin text-blue-500 mx-auto mb-3" />
                    <p className="text-slate-400 text-sm font-bold">Загрузка задачи...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-full bg-slate-50 dark:bg-slate-950">
                <div className="text-center">
                    <AlertCircle size={36} className="text-red-400 mx-auto mb-3" />
                    <p className="text-slate-700 dark:text-slate-200 font-bold mb-2">{error}</p>
                    <button
                        onClick={() => navigate('/tasks')}
                        className="text-blue-500 hover:text-blue-700 text-sm font-bold"
                    >
                        Вернуться к списку задач
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950 overflow-hidden">
            {/* Header */}
            <ProblemHeader
                polygonId={polygonId}
                name={problem?.name ?? ''}
                problemType={problemType}
                onProblemTypeChange={handleProblemTypeChange}
                savingType={savingType}
                onBack={() => navigate('/tasks')}
            />

            {/* Body */}
            <div className="flex flex-1 min-h-0 overflow-hidden">
                {/* Left: tabs + content */}
                <div className="flex-1 min-w-0 flex flex-col overflow-hidden bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800">
                    {/* Tab bar */}
                    <div className="shrink-0 flex border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-x-auto">
                        {TABS.map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => changeTab(tab.id)}
                                className={`flex items-center gap-1.5 px-4 py-3 text-xs font-bold whitespace-nowrap
                                    border-b-2 transition-all
                                    ${activeTab === tab.id
                                        ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-50/50 dark:bg-blue-900/10'
                                        : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50'
                                    }`}
                            >
                                {tab.icon}
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    {/* Tab content. reloadKey bumps remount tabs after an AI edit. */}
                    <div className="flex-1 overflow-y-auto">
                        {activeTab === 'statement' && (
                            <StatementTab
                                key={`statement-${reloadKey}`}
                                polygonId={polygonId}
                                sessionId={session?.session_id ?? null}
                                interactive={problemType === 'interactive'}
                                enableGroups={Boolean((session?.problem_settings as any)?.enable_groups)}
                                enablePoints={Boolean((session?.problem_settings as any)?.enable_points)}
                            />
                        )}
                        {activeTab === 'files' && (
                            <FilesTab
                                key={`files-${reloadKey}`}
                                polygonId={polygonId}
                                sessionId={session?.session_id ?? null}
                            />
                        )}
                        {activeTab === 'tests' && (
                            <TestsTab key={`tests-${reloadKey}`} polygonId={polygonId} />
                        )}
                        {activeTab === 'packages' && (
                            <PackagesTab
                                key={`packages-${reloadKey}`}
                                polygonId={polygonId}
                                sessionId={session?.session_id ?? null}
                            />
                        )}
                    </div>
                </div>

                {/* Resize handle */}
                <div
                    onMouseDown={startChatResize}
                    title="Потяните, чтобы изменить ширину чата"
                    className="w-1.5 shrink-0 cursor-col-resize bg-transparent
                               hover:bg-blue-400/60 active:bg-blue-500 transition-colors -ml-1.5 z-10"
                />

                {/* Right: chat panel */}
                <div style={{ width: chatWidth }} className="shrink-0 flex min-h-0">
                    <ChatPanel
                        sessionId={session?.session_id ?? null}
                        model={chatModel}
                        onModelChange={handleModelChange}
                        polygonId={polygonId}
                        initialMessages={session?.chat_log ?? []}
                        onModified={() => setReloadKey(k => k + 1)}
                    />
                </div>
            </div>
        </div>
    );
};
