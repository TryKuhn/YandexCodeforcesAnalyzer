// pages/tasks/TaskPage.tsx

import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2, AlertCircle, FileText, Folder, TestTube, Package } from 'lucide-react';
import { api } from '../../api/instance';
import { aiApi, isActive, type AiEvent } from '../../api/ai';
import { DEFAULT_AI_MODEL } from '../../constants/aiModels';
import { ProblemHeader } from './components/ProblemHeader';
import { ChatPanel } from './components/ChatPanel';
import { EventToasts } from './components/EventToasts';
import { StatementTab } from './tabs/StatementTab';
import { FilesTab } from './tabs/FilesTab';
import { TestsTab } from './tabs/TestsTab';
import { PackagesTab } from './tabs/PackagesTab';
import { useAiSession } from './useAiSession';

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

interface TestRow { group?: string | null; points?: number | null }

type TabId = 'statement' | 'files' | 'tests' | 'packages';

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: 'statement', label: 'Условие',  icon: <FileText size={14} /> },
    { id: 'files',     label: 'Файлы',    icon: <Folder size={14} /> },
    { id: 'tests',     label: 'Тесты',    icon: <TestTube size={14} /> },
    { id: 'packages',  label: 'Пакеты',   icon: <Package size={14} /> },
];

// Chat panel resize bounds
const CHAT_MIN_W = 280;
const CHAT_DEFAULT_W = 340;
const CHAT_WIDTH_KEY = 'taskChatPanelWidth';

const readChatWidth = () => {
    try {
        const saved = Number(localStorage.getItem(CHAT_WIDTH_KEY));
        return saved >= CHAT_MIN_W ? saved : CHAT_DEFAULT_W;
    } catch {
        return CHAT_DEFAULT_W;
    }
};

// ─── Component ───────────────────────────────────────────────────────────────

export const TaskPage = () => {
    const { polygonId: polygonIdStr } = useParams<{ polygonId: string }>();
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const polygonId = Number(polygonIdStr);

    const initialTab = TABS.some(t => t.id === searchParams.get('tab'))
        ? (searchParams.get('tab') as TabId)
        : 'statement';
    const [activeTab, setActiveTab] = useState<TabId>(initialTab);

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
    const [scoringFlags, setScoringFlags] = useState({ groups: false, points: false });
    const [mobileView, setMobileView] = useState<'content' | 'chat'>('content');
    const [chatWidth, setChatWidth] = useState(readChatWidth);
    const [savingType, setSavingType] = useState(false);
    const [reloadKey, setReloadKey] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [toasts, setToasts] = useState<AiEvent[]>([]);

    const bumpTabs = useCallback(() => setReloadKey(k => k + 1), []);

    const ai = useAiSession(polygonId, {
        // something changed in Polygon behind our back, or a build finished; the tabs
        // are not remounted automatically (that would drop unsaved edits) -- the toast
        // offers to reload them
        onEvents: events => setToasts(prev => [...prev, ...events].slice(-4)),
        // the AI finished: show the new state, but only when it changed files
        onRunFinished: run => {
            aiApi.run(run.id)
                .then(done => {
                    const changed = done.result?.changed;
                    if (Array.isArray(changed) && changed.length) bumpTabs();
                })
                .catch(() => bumpTabs());
        },
    });
    const dismissToast = useCallback((id: number) => setToasts(prev => prev.filter(t => t.id !== id)), []);
    const reloadFromToast = useCallback((id: number) => {
        bumpTabs();
        setToasts(prev => prev.filter(t => t.id !== id));
    }, [bumpTabs]);

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
            setChatWidth(w => {
                try { localStorage.setItem(CHAT_WIDTH_KEY, String(w)); } catch { /* private mode */ }
                return w;
            });
        };
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
    };

    useEffect(() => {
        if (!polygonId) return;
        setLoading(true);
        setError(null);
        api.get(`/polygon/problems/${polygonId}`)
            .then(res => setProblem(res.data as PolygonProblem))
            .catch(e => setError(e?.response?.data?.detail || 'Ошибка загрузки задачи'))
            .finally(() => setLoading(false));
    }, [polygonId]);

    // whether the problem has groups / points: the statement shows «Система оценки» then
    useEffect(() => {
        if (!polygonId) return;
        api.get<TestRow[]>(`/polygon/problems/${polygonId}/tests/tests`, { params: { no_inputs: true } })
            .then(res => {
                const tests = res.data || [];
                setScoringFlags({
                    groups: tests.some(t => t.group),
                    points: tests.some(t => t.points !== null && t.points !== undefined),
                });
            })
            .catch(() => { /* not critical */ });
    }, [polygonId, reloadKey]);

    const handleModelChange = async (model: string) => {
        try { await ai.update({ model }); } catch { /* keep the old one */ }
    };

    const handleProblemTypeChange = async (problemType: string) => {
        setSavingType(true);
        try { await ai.update({ problem_type: problemType }); } catch { /* unchanged */ } finally { setSavingType(false); }
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
                    <button onClick={() => navigate('/tasks')} className="text-blue-500 hover:text-blue-700 text-sm font-bold">
                        Вернуться к списку задач
                    </button>
                </div>
            </div>
        );
    }

    const sessionId = ai.sessionId;
    const problemType = ai.session?.problem_type ?? (problem?.interactive ? 'interactive' : 'regular');
    const busy = isActive(ai.activeRun);

    return (
        <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950 overflow-hidden">
            <ProblemHeader
                polygonId={polygonId}
                name={problem?.name ?? ''}
                problemType={problemType}
                onProblemTypeChange={handleProblemTypeChange}
                savingType={savingType || !sessionId}
                onBack={() => navigate('/tasks')}
                latestBuild={ai.latestBuild}
                activeRun={ai.activeRun}
                lastSyncedAt={ai.lastSyncedAt}
                syncError={ai.syncError}
                syncing={ai.syncing}
                onSync={ai.sync}
                onOpenPackages={() => changeTab('packages')}
            />

            {/* Mobile editor/chat switch (desktop shows both side by side) */}
            <div className="md:hidden shrink-0 flex border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                {([['content', 'Редактор'], ['chat', 'AI Чат']] as const).map(([id, label]) => (
                    <button
                        key={id}
                        onClick={() => setMobileView(id)}
                        className={`flex-1 py-2.5 text-xs font-bold transition-colors border-b-2
                            ${mobileView === id
                                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                                : 'border-transparent text-slate-500 dark:text-slate-400'}`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            <div className="flex flex-1 min-h-0 overflow-hidden">
                <div className={`${mobileView === 'content' ? 'flex' : 'hidden'} md:flex
                    flex-1 min-w-0 flex-col overflow-hidden bg-white dark:bg-slate-900
                    md:border-r border-slate-200 dark:border-slate-800`}>
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

                    {/* reloadKey remounts the tabs after an AI edit or a change on Polygon */}
                    <div className="flex-1 overflow-y-auto">
                        {activeTab === 'statement' && (
                            <StatementTab
                                key={`statement-${reloadKey}`}
                                polygonId={polygonId}
                                sessionId={sessionId}
                                interactive={problemType === 'interactive'}
                                enableGroups={scoringFlags.groups}
                                enablePoints={scoringFlags.points}
                            />
                        )}
                        {activeTab === 'files' && (
                            <FilesTab key={`files-${reloadKey}`} polygonId={polygonId} sessionId={sessionId} />
                        )}
                        {activeTab === 'tests' && (
                            <TestsTab
                                key={`tests-${reloadKey}`}
                                polygonId={polygonId}
                                sessionId={sessionId}
                                busy={busy}
                                onRunStarted={ai.track}
                            />
                        )}
                        {activeTab === 'packages' && (
                            <PackagesTab
                                polygonId={polygonId}
                                sessionId={sessionId}
                                latestBuild={ai.latestBuild}
                                activeRun={ai.activeRun}
                                onRunStarted={ai.track}
                            />
                        )}
                    </div>
                </div>

                <div
                    onMouseDown={startChatResize}
                    title="Потяните, чтобы изменить ширину чата"
                    className="hidden md:block w-1.5 shrink-0 cursor-col-resize bg-transparent
                               hover:bg-blue-400/60 active:bg-blue-500 transition-colors -ml-1.5 z-10"
                />

                <div
                    style={{ width: chatWidth }}
                    className={`${mobileView === 'chat' ? 'flex' : 'hidden'} md:flex shrink-0 min-h-0 max-md:!w-full`}
                >
                    <ChatPanel
                        sessionId={sessionId}
                        model={ai.session?.model ?? DEFAULT_AI_MODEL}
                        onModelChange={handleModelChange}
                        messages={ai.messages}
                        activeRun={ai.activeRun}
                        onSend={ai.send}
                        onCancel={ai.cancel}
                        error={ai.error}
                    />
                </div>
            </div>

            <EventToasts events={toasts} onDismiss={dismissToast} onReload={reloadFromToast} />
        </div>
    );
};
