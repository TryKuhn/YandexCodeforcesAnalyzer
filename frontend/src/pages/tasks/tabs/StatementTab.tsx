// pages/tasks/tabs/StatementTab.tsx

import { useState, useEffect, useRef } from 'react';
import { Loader2, RefreshCw, Save, AlertCircle, Eye, Edit2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { api } from '../../../api/instance';

interface Props {
    polygonId: number;
    sessionId: string | null;
    interactive?: boolean;
    enableGroups?: boolean;
}

interface Statement {
    encoding: string;
    name: string;
    legend: string;
    input: string;
    output: string;
    scoring?: string;
    interaction?: string;
    notes?: string;
    tutorial?: string;
}

interface ProblemInfo {
    inputFile: string;
    outputFile: string;
    timeLimit: number;
    memoryLimit: number;
    [key: string]: unknown;
}

interface SampleTest {
    index: number;
    input: string;
    loading?: boolean;
}

const LANGS = ['russian', 'english'];
const AUTO_SAVE_MS = 45_000;

type StatementKey = keyof Statement;
interface FieldDef { key: StatementKey; label: string; rows: number; conditional?: boolean }

const BASE_FIELDS: FieldDef[] = [
    { key: 'name',    label: 'Название',        rows: 1 },
    { key: 'legend',  label: 'Условие',         rows: 8 },
    { key: 'input',   label: 'Входные данные',  rows: 3 },
    { key: 'output',  label: 'Выходные данные', rows: 3 },
    { key: 'notes',   label: 'Примечания',      rows: 3 },
    { key: 'tutorial', label: 'Разбор',         rows: 5 },
];
const SCORING_FIELD: FieldDef     = { key: 'scoring',     label: 'Система оценивания', rows: 3, conditional: true };
const INTERACTION_FIELD: FieldDef = { key: 'interaction', label: 'Взаимодействие',     rows: 3, conditional: true };

// Fields that support KaTeX preview
const PREVIEW_FIELDS = new Set(['legend', 'input', 'output', 'notes', 'tutorial', 'scoring', 'interaction']);

function renderLatex(src: string) {
    return src
        .replace(/\\\[/g, '$$$$')
        .replace(/\\\]/g, '$$$$')
        .replace(/\\\(/g, '$')
        .replace(/\\\)/g, '$')
        .replace(/\\texttt\{([^{}]*)\}/g, '`$1`')
        .replace(/\\t\{([^{}]*)\}/g, '`$1`');
}

export const StatementTab = ({ polygonId, sessionId: _sessionId, interactive = false, enableGroups = false }: Props) => {
    const [statements, setStatements]     = useState<Record<string, Statement>>({});
    const [activeLang, setActiveLang]     = useState('russian');
    const [editInfo, setEditInfo]         = useState<ProblemInfo | null>(null);
    const [sampleTests, setSampleTests]   = useState<SampleTest[]>([]);
    const [loading, setLoading]           = useState(true);
    const [syncing, setSyncing]           = useState(false);
    const [savingStatement, setSavingStatement] = useState(false);
    const [savingInfo, setSavingInfo]     = useState(false);
    const [error, setError]               = useState<string | null>(null);
    const [successMsg, setSuccessMsg]     = useState<string | null>(null);

    // Single active edit field (null = all in preview)
    const [activeEditField, setActiveEditField] = useState<string | null>(null);

    // Dirty flag — true when unsaved changes exist
    const isDirty = useRef(false);

    // Refs for latest values used in the auto-save interval
    const statementsRef  = useRef(statements);
    const activeLangRef  = useRef(activeLang);
    // Update refs after every render (no dependency array = runs every render)
    useEffect(() => { statementsRef.current = statements; });
    useEffect(() => { activeLangRef.current = activeLang; });

    // Settings toggles (local state for immediate visual feedback)
    const [isInteractive, setIsInteractive]   = useState(interactive);
    const [hasGroups, setHasGroups]           = useState(enableGroups);
    const [hasPoints, setHasPoints]           = useState(false);
    const [togglingInteractive, setTogglingInteractive] = useState(false);
    const [togglingGroups, setTogglingGroups]           = useState(false);
    const [togglingPoints, setTogglingPoints]           = useState(false);

    const currentStatement = statements[activeLang] || ({} as Statement);

    // ── Auto-save interval ───────────────────────────────────────────────────
    useEffect(() => {
        const timer = setInterval(() => {
            if (!isDirty.current) return;
            const lang = activeLangRef.current;
            const stmt = statementsRef.current[lang];
            if (!stmt) return;
            isDirty.current = false;
            api.patch(`/polygon/problems/${polygonId}/statement`, { lang, ...stmt }).catch(() => {});
        }, AUTO_SAVE_MS);
        return () => clearInterval(timer);
    }, [polygonId]);

    // ── Data loading ─────────────────────────────────────────────────────────
    const load = async () => {
        setLoading(true);
        setError(null);
        try {
            const [stmtRes, infoRes, testsRes] = await Promise.allSettled([
                api.get(`/polygon/problems/${polygonId}/statement`),
                api.get(`/polygon/problems/${polygonId}/info`),
                api.get(`/polygon/problems/${polygonId}/tests/tests?no_inputs=true`),
            ]);

            if (stmtRes.status === 'fulfilled') {
                const data = stmtRes.value.data;
                if (typeof data === 'object' && !Array.isArray(data)) {
                    setStatements(data as Record<string, Statement>);
                }
            }
            if (infoRes.status === 'fulfilled') {
                const d = infoRes.value.data;
                setEditInfo({ ...d });
            }
            if (testsRes.status === 'fulfilled') {
                const tests: any[] = testsRes.value.data || [];
                const samples = tests.filter((t: any) => t.useInStatements || t.use_in_statements);
                setSampleTests(samples.map((t: any) => ({
                    index: t.index,
                    input: t.input || '',
                    loading: !t.input,
                })));
                for (const t of samples) {
                    if (!t.input) loadSampleInput(t.index);
                }
            }
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка загрузки');
        } finally {
            setLoading(false);
        }
    };

    const loadSampleInput = async (index: number) => {
        try {
            const res = await api.get(`/polygon/problems/${polygonId}/tests/tests/${index}/input`);
            const input = res.data.content ?? res.data ?? '';
            setSampleTests(prev => prev.map(t =>
                t.index === index ? { ...t, input, loading: false } : t
            ));
        } catch {
            setSampleTests(prev => prev.map(t =>
                t.index === index ? { ...t, input: '(не удалось загрузить)', loading: false } : t
            ));
        }
    };

    useEffect(() => { load(); }, [polygonId]);

    // ── Save helpers ─────────────────────────────────────────────────────────

    // Silent background save (used on field switch and auto-save)
    const bgSave = (stmts: Record<string, Statement>, lang: string) => {
        const stmt = stmts[lang];
        if (!stmt || !isDirty.current) return;
        isDirty.current = false;
        api.patch(`/polygon/problems/${polygonId}/statement`, { lang, ...stmt }).catch(() => {});
    };

    const handleSaveStatement = async () => {
        isDirty.current = false;
        setSavingStatement(true);
        try {
            await api.patch(`/polygon/problems/${polygonId}/statement`, {
                lang: activeLang,
                ...currentStatement,
            });
            showSuccess('Условие сохранено');
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка сохранения');
        } finally {
            setSavingStatement(false);
        }
    };

    const handleSaveInfo = async () => {
        if (!editInfo) return;
        setSavingInfo(true);
        try {
            await api.patch(`/polygon/problems/${polygonId}/info`, editInfo);
            showSuccess('Настройки сохранены');
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка сохранения');
        } finally {
            setSavingInfo(false);
        }
    };

    const handleSync = async () => {
        setSyncing(true);
        try {
            await api.post(`/polygon/problems/${polygonId}/sync`);
            await load();
            showSuccess('Синхронизировано с Polygon');
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка синхронизации');
        } finally {
            setSyncing(false);
        }
    };

    const showSuccess = (msg: string) => {
        setSuccessMsg(msg);
        setTimeout(() => setSuccessMsg(null), 2500);
    };

    // ── Field editing ────────────────────────────────────────────────────────

    const updateField = (key: StatementKey, value: string) => {
        isDirty.current = true;
        setStatements(prev => ({
            ...prev,
            [activeLang]: { ...(prev[activeLang] || {} as Statement), [key]: value },
        }));
    };

    // Activate a field for editing (saves previous if dirty)
    const handleActivate = (key: string) => {
        if (activeEditField === key) return;
        bgSave(statements, activeLang);
        setActiveEditField(key);
    };

    // Deactivate current field (saves + goes back to preview)
    const handleDeactivate = () => {
        bgSave(statements, activeLang);
        setActiveEditField(null);
    };

    // Language tab switch (saves + resets active field)
    const handleLangChange = (newLang: string) => {
        bgSave(statements, activeLang);
        setActiveEditField(null);
        setActiveLang(newLang);
    };

    // ── Settings toggles ─────────────────────────────────────────────────────

    const handleToggleInteractive = async () => {
        const next = !isInteractive;
        setIsInteractive(next);
        setTogglingInteractive(true);
        try {
            await api.patch(`/polygon/problems/${polygonId}/info`, { interactive: next });
        } catch { setIsInteractive(!next); }
        finally { setTogglingInteractive(false); }
    };

    const handleToggleGroups = async () => {
        const next = !hasGroups;
        setHasGroups(next);
        setTogglingGroups(true);
        try {
            await api.post(`/polygon/problems/${polygonId}/settings/enable-groups`, { enable: next });
        } catch { setHasGroups(!next); }
        finally { setTogglingGroups(false); }
    };

    const handleTogglePoints = async () => {
        const next = !hasPoints;
        setHasPoints(next);
        setTogglingPoints(true);
        try {
            await api.post(`/polygon/problems/${polygonId}/settings/enable-points`, { enable: next });
        } catch { setHasPoints(!next); }
        finally { setTogglingPoints(false); }
    };

    // ── Build fields list ────────────────────────────────────────────────────
    const fields: FieldDef[] = [...BASE_FIELDS];
    if (hasGroups) fields.splice(4, 0, SCORING_FIELD);
    if (isInteractive) fields.splice(hasGroups ? 5 : 4, 0, INTERACTION_FIELD);

    // ── Render ───────────────────────────────────────────────────────────────

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <Loader2 size={28} className="animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <div className="p-4 lg:p-6 space-y-6 max-w-3xl mx-auto">
            {/* Toolbar */}
            <div className="flex items-center gap-3 flex-wrap">
                <div className="flex bg-slate-100 dark:bg-slate-800 rounded-xl p-0.5 gap-0.5">
                    {LANGS.map(lang => (
                        <button
                            key={lang}
                            onClick={() => handleLangChange(lang)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all
                                ${activeLang === lang
                                    ? 'bg-white dark:bg-slate-700 shadow-sm text-blue-600 dark:text-blue-400'
                                    : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                                }`}
                        >
                            {lang === 'russian' ? 'Русский' : 'English'}
                        </button>
                    ))}
                </div>

                <div className="flex-1" />

                {successMsg && (
                    <span className="text-xs text-green-600 dark:text-green-400 font-bold">{successMsg}</span>
                )}

                <button
                    onClick={handleSync}
                    disabled={syncing}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold
                               bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300
                               hover:bg-slate-200 dark:hover:bg-slate-700 transition-all disabled:opacity-50"
                >
                    {syncing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                    Синхронизировать с Polygon
                </button>

                <button
                    onClick={handleSaveStatement}
                    disabled={savingStatement}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold
                               bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50"
                >
                    {savingStatement ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                    Сохранить условие
                </button>
            </div>

            {error && (
                <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-xl text-sm">
                    <AlertCircle size={16} />
                    {error}
                    <button onClick={() => setError(null)} className="ml-auto text-xs underline">Закрыть</button>
                </div>
            )}

            {/* Problem info */}
            {editInfo && (
                <div className="border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
                    <div className="px-4 py-2.5 bg-slate-50 dark:bg-slate-800/50 text-xs font-bold text-slate-600 dark:text-slate-300">
                        Настройки задачи
                    </div>

                    {/* Toggles row */}
                    <div className="px-4 pt-3 pb-1 flex items-center gap-4 flex-wrap">
                        <SettingToggle
                            label="Интерактивная"
                            checked={isInteractive}
                            loading={togglingInteractive}
                            onChange={handleToggleInteractive}
                        />
                        <SettingToggle
                            label="Группы тестов"
                            checked={hasGroups}
                            loading={togglingGroups}
                            onChange={handleToggleGroups}
                        />
                        <SettingToggle
                            label="Баллы"
                            checked={hasPoints}
                            loading={togglingPoints}
                            onChange={handleTogglePoints}
                        />
                    </div>

                    <div className="p-4 grid grid-cols-2 gap-3">
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 mb-1">Входной файл</label>
                            <input
                                value={editInfo.inputFile ?? ''}
                                onChange={e => setEditInfo(prev => prev ? { ...prev, inputFile: e.target.value } : prev)}
                                placeholder="stdin"
                                className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-slate-200"
                            />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 mb-1">Выходной файл</label>
                            <input
                                value={editInfo.outputFile ?? ''}
                                onChange={e => setEditInfo(prev => prev ? { ...prev, outputFile: e.target.value } : prev)}
                                placeholder="stdout"
                                className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-slate-200"
                            />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 mb-1">Лимит времени (мс)</label>
                            <input
                                type="number"
                                value={editInfo.timeLimit ?? 2000}
                                onChange={e => setEditInfo(prev => prev ? { ...prev, timeLimit: Number(e.target.value) } : prev)}
                                className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-slate-200"
                            />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 mb-1">Лимит памяти (МБ)</label>
                            <input
                                type="number"
                                value={editInfo.memoryLimit ?? 256}
                                onChange={e => setEditInfo(prev => prev ? { ...prev, memoryLimit: Number(e.target.value) } : prev)}
                                className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                            />
                        </div>
                    </div>
                    <div className="px-4 pb-4 flex justify-end">
                        <button
                            onClick={handleSaveInfo}
                            disabled={savingInfo}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold
                                       bg-slate-600 hover:bg-slate-700 text-white transition-all disabled:opacity-50"
                        >
                            {savingInfo ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                            Сохранить настройки
                        </button>
                    </div>
                </div>
            )}

            {/* Statement fields */}
            <div className="space-y-4">
                {fields.map(({ key, label, rows }) => {
                    const value = (currentStatement[key] as string) || '';
                    const canPreview = PREVIEW_FIELDS.has(key as string);
                    const isEditing = activeEditField === key;
                    const showPreview = canPreview && !!value && !isEditing;

                    return (
                        <div key={key}>
                            <div className="flex items-center justify-between mb-1.5">
                                <label className="text-xs font-bold text-slate-600 dark:text-slate-400">
                                    {label}
                                </label>
                                {canPreview && (value || isEditing) && (
                                    <button
                                        onClick={() => isEditing ? handleDeactivate() : handleActivate(key)}
                                        className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-lg
                                                   bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-blue-500
                                                   hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all"
                                    >
                                        {isEditing ? <Eye size={10} /> : <Edit2 size={10} />}
                                        {isEditing ? 'Превью' : 'Редактировать'}
                                    </button>
                                )}
                            </div>

                            {showPreview ? (
                                <div
                                    onClick={() => handleActivate(key)}
                                    title="Нажмите для редактирования"
                                    className="cursor-text min-h-[44px] text-sm bg-slate-50 dark:bg-slate-800/50
                                               border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2
                                               prose prose-sm dark:prose-invert max-w-none dark:text-slate-200
                                               prose-p:my-1 prose-pre:bg-slate-100 dark:prose-pre:bg-slate-800"
                                >
                                    <ReactMarkdown
                                        remarkPlugins={[remarkMath]}
                                        rehypePlugins={[[rehypeKatex, { macros: { '\\texttt': '\\mathtt{#1}' } }]]}
                                    >
                                        {renderLatex(value)}
                                    </ReactMarkdown>
                                </div>
                            ) : (
                                (isEditing || !canPreview) && (
                                    <textarea
                                        value={value}
                                        onChange={e => updateField(key, e.target.value)}
                                        rows={rows}
                                        autoFocus={isEditing}
                                        className="w-full text-sm font-mono bg-slate-50 dark:bg-slate-800
                                                   border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2
                                                   outline-none dark:text-slate-200 resize-y
                                                   focus:border-blue-500 transition-all"
                                    />
                                )
                            )}

                            {/* Empty preview-field placeholder (not editing, no value) */}
                            {canPreview && !value && !isEditing && (
                                <div
                                    onClick={() => handleActivate(key)}
                                    className="cursor-text min-h-[44px] bg-slate-50 dark:bg-slate-800/50
                                               border border-dashed border-slate-300 dark:border-slate-700
                                               rounded-xl px-3 py-2 flex items-center justify-center"
                                >
                                    <span className="text-xs text-slate-400">Нажмите для редактирования</span>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Samples */}
            {sampleTests.length > 0 && (
                <div>
                    <h3 className="text-sm font-bold text-slate-700 dark:text-slate-200 mb-3">
                        Примеры (из тестов)
                    </h3>
                    <div className="space-y-3">
                        {sampleTests.map(test => (
                            <div
                                key={test.index}
                                className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden"
                            >
                                <div className="px-3 py-1.5 bg-slate-50 dark:bg-slate-800/50 text-[11px] font-bold text-slate-500">
                                    Пример {test.index}
                                </div>
                                <div className="p-3">
                                    {test.loading ? (
                                        <Loader2 size={14} className="animate-spin text-slate-400" />
                                    ) : (
                                        <pre className="text-xs font-mono text-slate-700 dark:text-slate-300 whitespace-pre-wrap">
                                            {test.input || '(нет данных)'}
                                        </pre>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

// ── Helper component ──────────────────────────────────────────────────────────

interface SettingToggleProps {
    label: string;
    checked: boolean;
    loading: boolean;
    onChange: () => void;
}

const SettingToggle = ({ label, checked, loading, onChange }: SettingToggleProps) => (
    <label className="flex items-center gap-2 cursor-pointer select-none">
        {loading ? (
            <Loader2 size={14} className="animate-spin text-blue-500 shrink-0" />
        ) : (
            <input
                type="checkbox"
                checked={checked}
                onChange={onChange}
                className="w-4 h-4 cursor-pointer accent-blue-500"
            />
        )}
        <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
            {label}
        </span>
    </label>
);
