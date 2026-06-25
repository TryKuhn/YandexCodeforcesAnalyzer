// pages/tasks/tabs/StatementTab.tsx

import { useState, useEffect, useRef } from 'react';
import { Loader2, RefreshCw, Save, AlertCircle, Eye, Edit2, Tag, X, Plus, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { api } from '../../../api/instance';

interface Props {
    polygonId: number;
    sessionId: string | null;
    interactive?: boolean;
    enableGroups?: boolean;
    enablePoints?: boolean;
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

// ── Polygon LaTeX → Markdown converter ──────────────────────────────────────
// Handles balanced braces (so \texttt{...\{\}...} works), tabular → md tables,
// nested commands, escaped chars and images.

// Return [content, indexAfterClosingBrace] for a group starting at the `{` at `start`.
function extractGroup(str: string, start: number): [string, number] {
    let depth = 0;
    for (let i = start; i < str.length; i++) {
        const c = str[i];
        if (c === '\\') { i++; continue; }       // skip escaped char
        if (c === '{') depth++;
        else if (c === '}') { depth--; if (depth === 0) return [str.slice(start + 1, i), i + 1]; }
    }
    return [str.slice(start + 1), str.length];
}

// Replace every \name{...} (balanced) using `wrap(content)`.
function replaceCmd(s: string, name: string, wrap: (c: string) => string): string {
    const re = new RegExp('\\\\' + name + '\\s*\\{', 'g');
    let out = '', last = 0, m: RegExpExecArray | null;
    while ((m = re.exec(s)) !== null) {
        const braceIdx = m.index + m[0].length - 1;
        const [content, end] = extractGroup(s, braceIdx);
        out += s.slice(last, m.index) + wrap(content);
        last = end;
        re.lastIndex = end;
    }
    return out + s.slice(last);
}

const unescapeLatex = (s: string) => s.replace(/\\([{}_&%#])/g, '$1');

// Apply inline formatting commands (recursively for nestable ones).
function processInline(s: string): string {
    s = replaceCmd(s, 'texttt', c => '`' + unescapeLatex(c) + '`');
    s = replaceCmd(s, 't', c => '`' + unescapeLatex(c) + '`');
    s = replaceCmd(s, 'textbf', c => '**' + processInline(c) + '**');
    s = replaceCmd(s, 'textit', c => '*' + processInline(c) + '*');
    s = replaceCmd(s, 'emph', c => '*' + processInline(c) + '*');
    s = replaceCmd(s, 'sout', c => '~~' + processInline(c) + '~~');
    s = replaceCmd(s, 'textsc', c => processInline(c));
    s = replaceCmd(s, 'textsf', c => processInline(c));
    s = replaceCmd(s, 'underline', c => processInline(c));
    // Size switches — drop the sizing, keep the content.
    for (const sz of ['tiny', 'scriptsize', 'small', 'normalsize', 'large', 'Large', 'LARGE', 'huge', 'Huge']) {
        s = replaceCmd(s, sz, c => processInline(c));
    }
    return s;
}

// Convert a \begin{tabular}{spec} ... \end{tabular} body into a Markdown table.
function tabularToMarkdown(body: string): string {
    let b = body.replace(/^\s*\{[^}]*\}/, '');   // drop the column spec {|c|c|...}
    const rows = b.split('\\\\')
        .map(r => r.replace(/\\hline/g, '').trim())
        .filter(Boolean);
    if (!rows.length) return '';
    const cells = rows.map(r => r.split('&').map(c => processInline(c.trim()).replace(/\n/g, ' ').trim() || ' '));
    const header = cells[0];
    let md = '\n\n| ' + header.join(' | ') + ' |\n';
    md += '| ' + header.map(() => '---').join(' | ') + ' |\n';
    for (let i = 1; i < cells.length; i++) md += '| ' + cells[i].join(' | ') + ' |\n';
    return md + '\n';
}

function renderLatex(src: string): string {
    let s = src;

    // Protect code from every other rewrite below (dashes, quotes, math, inline
    // commands would all corrupt source code). Stash blocks/inline code as
    // placeholders now and restore them as Markdown code at the very end.
    // Polygon's code environment is lstlisting; verbatim is also handled since
    // models sometimes emit it (and it must not leak raw into the preview).
    const codeStash: string[] = [];
    const stashCode = (code: string, inline: boolean): string => {
        // @@-sentinel: survives indent-strip and every text rewrite below
        // (no <<, ---, $, backslash or brace chars); restored last.
        const token = `@@CODE${codeStash.length}@@`;
        codeStash.push(inline
            ? '`' + code.replace(/\n/g, ' ') + '`'
            : '\n\n```\n' + code.replace(/^\n+|\s+$/g, '') + '\n```\n\n');
        return token;
    };
    s = s.replace(/\\begin\{(?:verbatim|lstlisting)\}([\s\S]*?)\\end\{(?:verbatim|lstlisting)\}/g,
        (_m, body) => stashCode(body, false));
    // \verb<delim>...<delim> and \verb*<delim>...<delim> (any delimiter char)
    s = s.replace(/\\verb\*?([^a-zA-Z0-9\s])([\s\S]*?)\1/g, (_m, _d, body) => stashCode(body, true));

    // Guillemets and dashes first (before tables, whose separators use --- )
    s = s.replace(/<</g, '«').replace(/>>/g, '»');
    s = s.replace(/---/g, '—').replace(/(?<!-)--(?!-)/g, '–');

    // \begin{center} ... \end{center} — just drop the wrapper
    s = s.replace(/\\begin\{center\}/g, '\n').replace(/\\end\{center\}/g, '\n');

    // Tabular → Markdown table
    s = s.replace(/\\begin\{tabular\}([\s\S]*?)\\end\{tabular\}/g,
        (_m, body) => tabularToMarkdown(body));

    // Links: \href{url}{text} → [text](url); \url{url} → bare link
    s = s.replace(/\\href\s*\{([^}]*)\}\s*\{([^}]*)\}/g, (_m, url, text) => `[${text}](${url})`);
    s = s.replace(/\\url\s*\{([^}]*)\}/g, (_m, url) => `<${url}>`);

    // Images → italic placeholder (resource files aren't served inline)
    s = s.replace(/\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}/g,
        (_m, f) => `\n\n*[изображение: ${f}]*\n\n`);

    // Lists
    s = s.replace(/\\begin\{enumerate\}([\s\S]*?)\\end\{enumerate\}/g, (_m, body) => {
        const items = body.split(/\\item/).map((x: string) => x.trim()).filter(Boolean);
        return '\n\n' + items.map((it: string, i: number) => `${i + 1}. ${it}`).join('\n') + '\n\n';
    });
    s = s.replace(/\\begin\{itemize\}([\s\S]*?)\\end\{itemize\}/g, (_m, body) => {
        const items = body.split(/\\item/).map((x: string) => x.trim()).filter(Boolean);
        return '\n\n' + items.map((it: string) => `- ${it}`).join('\n') + '\n\n';
    });
    s = s.replace(/\\item\s*/g, '\n- ');

    // Inline formatting (balanced braces, nested)
    s = processInline(s);

    // Math delimiters
    s = s.replace(/\\\[/g, '$$').replace(/\\\]/g, '$$');
    s = s.replace(/\\\(/g, '$').replace(/\\\)/g, '$');

    // Unescape remaining escaped chars outside code
    s = unescapeLatex(s);

    // Strip leading indentation so aligned LaTeX isn't seen as a code block
    s = s.split('\n').map(l => l.replace(/^[ \t]+/, '')).join('\n');

    // Restore stashed code (verbatim/lstlisting/\verb) as Markdown code, after
    // all rewriting so its contents were never altered.
    s = s.replace(/@@CODE(\d+)@@/g, (_m, i) => codeStash[Number(i)] ?? '');

    return s;
}

export const StatementTab = ({ polygonId, sessionId, interactive = false, enableGroups = false, enablePoints = false }: Props) => {
    const [statements, setStatements]     = useState<Record<string, Statement>>({});
    const [activeLang, setActiveLang]     = useState('russian');
    const [editInfo, setEditInfo]         = useState<ProblemInfo | null>(null);
    const [sampleTests, setSampleTests]   = useState<SampleTest[]>([]);

    // Tags
    const [tags, setTags]                 = useState<string[]>([]);
    const [tagInput, setTagInput]         = useState('');
    const [savingTags, setSavingTags]     = useState(false);
    const [suggestingTags, setSuggesting] = useState(false);
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

    // Settings toggles (local state for immediate visual feedback).
    // Interactivity is driven solely by the problem-type selector in the header
    // (the `interactive` prop) — there is no separate checkbox here.
    const [hasGroups, setHasGroups]           = useState(enableGroups);
    const [hasPoints, setHasPoints]           = useState(enablePoints);
    const [togglingGroups, setTogglingGroups]           = useState(false);
    const [togglingPoints, setTogglingPoints]           = useState(false);
    const [generatingScoring, setGeneratingScoring]     = useState(false);

    // Keep toggles in sync if the session settings arrive after first render.
    useEffect(() => { setHasGroups(enableGroups); }, [enableGroups]);
    useEffect(() => { setHasPoints(enablePoints); }, [enablePoints]);

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
            const [stmtRes, infoRes, testsRes, tagsRes] = await Promise.allSettled([
                api.get(`/polygon/problems/${polygonId}/statement`),
                api.get(`/polygon/problems/${polygonId}/info`),
                api.get(`/polygon/problems/${polygonId}/tests/tests?no_inputs=true`),
                api.get(`/polygon/problems/${polygonId}/tags`),
            ]);

            if (tagsRes.status === 'fulfilled') {
                setTags(tagsRes.value.data?.tags ?? []);
            }

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
                // Infer groups/points from the actual tests (Polygon info has no such flag).
                if (tests.some((t: any) => t.group)) setHasGroups(true);
                if (tests.some((t: any) => t.points !== undefined && t.points !== null)) setHasPoints(true);
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

    // Background save (used on field switch and auto-save)
    const bgSave = (stmts: Record<string, Statement>, lang: string) => {
        const stmt = stmts[lang];
        if (!stmt || !isDirty.current) return;
        isDirty.current = false;
        api.patch(`/polygon/problems/${polygonId}/statement`, { lang, ...stmt })
            .then(() => showSuccess('Сохранено на Polygon'))
            .catch(() => { isDirty.current = true; }); // retry on next auto-save
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

    // ── Tags ─────────────────────────────────────────────────────────────────
    const persistTags = async (next: string[]) => {
        setSavingTags(true);
        try {
            await api.patch(`/polygon/problems/${polygonId}/tags`, { tags: next });
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка сохранения тегов');
        } finally {
            setSavingTags(false);
        }
    };

    const addTags = (incoming: string[]) => {
        const merged = [...tags];
        for (const raw of incoming) {
            const t = raw.trim();
            if (t && !merged.some(x => x.toLowerCase() === t.toLowerCase())) merged.push(t);
        }
        if (merged.length === tags.length) return;
        setTags(merged);
        persistTags(merged);
    };

    const removeTag = (tag: string) => {
        const next = tags.filter(t => t !== tag);
        setTags(next);
        persistTags(next);
    };

    const handleTagInputKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            if (tagInput.trim()) { addTags([tagInput]); setTagInput(''); }
        }
    };

    const suggestTags = async () => {
        if (!sessionId) return;
        setSuggesting(true);
        try {
            const res = await api.post('/ai/suggest-tags', { session_id: sessionId });
            addTags(res.data?.suggested_tags ?? []);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Не удалось получить теги от ИИ');
        } finally {
            setSuggesting(false);
        }
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

    // Persist a flag both on Polygon (immediate effect) and on the AI session
    // (so the toggle state survives a page reload).
    const persistSetting = async (key: 'enable_groups' | 'enable_points', value: boolean) => {
        if (sessionId) {
            await api.patch(`/ai/session/${sessionId}/problem-settings`, {
                settings: { [key]: value },
            }).catch(() => {});
        }
    };

    const handleToggleGroups = async () => {
        const next = !hasGroups;
        setHasGroups(next);
        setTogglingGroups(true);
        try {
            await api.post(`/polygon/problems/${polygonId}/settings/enable-groups`, { enable: next });
            await persistSetting('enable_groups', next);
            if (next && !currentStatement.scoring && currentStatement.legend) await generateScoring();
        } catch { setHasGroups(!next); }
        finally { setTogglingGroups(false); }
    };

    const handleTogglePoints = async () => {
        const next = !hasPoints;
        setHasPoints(next);
        setTogglingPoints(true);
        try {
            await api.post(`/polygon/problems/${polygonId}/settings/enable-points`, { enable: next });
            await persistSetting('enable_points', next);
            if (next && !currentStatement.scoring && currentStatement.legend) await generateScoring();
        } catch { setHasPoints(!next); }
        finally { setTogglingPoints(false); }
    };

    // Generate the scoring table (subtask plan) via the AI session and show it.
    const generateScoring = async () => {
        if (!sessionId) return;
        setGeneratingScoring(true);
        try {
            const res = await api.post('/ai/generate-scoring', { session_id: sessionId });
            const scoring = res.data?.scoring ?? '';
            setStatements(prev => ({
                ...prev,
                [activeLang]: { ...(prev[activeLang] || {} as Statement), scoring },
            }));
            // Persist the scoring section onto the Polygon statement too.
            await api.patch(`/polygon/problems/${polygonId}/statement`, {
                lang: activeLang, ...(statementsRef.current[activeLang] || {}), scoring,
            }).catch(() => {});
            showSuccess('Система оценивания сгенерирована');
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Не удалось сгенерировать систему оценивания');
        } finally {
            setGeneratingScoring(false);
        }
    };

    // ── Build fields list ────────────────────────────────────────────────────
    const fields: FieldDef[] = [...BASE_FIELDS];
    const hasScoring = hasGroups || hasPoints;
    if (hasScoring) fields.splice(4, 0, SCORING_FIELD);
    if (interactive) fields.splice(hasScoring ? 5 : 4, 0, INTERACTION_FIELD);

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

                    {/* Toggles row. Interactivity is controlled by the problem-type
                        selector in the header, not here. */}
                    <div className="px-4 pt-3 pb-1 flex items-center gap-4 flex-wrap">
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

                    <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
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

            {/* Tags */}
            <div className="border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
                <div className="px-4 py-2.5 bg-slate-50 dark:bg-slate-800/50 flex items-center gap-2">
                    <Tag size={13} className="text-slate-400" />
                    <span className="text-xs font-bold text-slate-600 dark:text-slate-300 flex-1">Теги</span>
                    {savingTags && <Loader2 size={12} className="animate-spin text-slate-400" />}
                    <button
                        onClick={suggestTags}
                        disabled={suggestingTags || !sessionId}
                        title={sessionId ? 'Предложить теги через ИИ' : 'Нет активной сессии'}
                        className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-lg
                                   bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400
                                   hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-all disabled:opacity-50"
                    >
                        {suggestingTags ? <Loader2 size={10} className="animate-spin" /> : <Sparkles size={10} />}
                        ИИ-теги
                    </button>
                </div>
                <div className="p-3 flex flex-wrap items-center gap-1.5">
                    {tags.map(tag => (
                        <span
                            key={tag}
                            className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold
                                       bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300"
                        >
                            {tag}
                            <button
                                onClick={() => removeTag(tag)}
                                className="hover:text-red-500 transition-colors"
                            >
                                <X size={10} />
                            </button>
                        </span>
                    ))}
                    <div className="flex items-center gap-1 min-w-[140px] flex-1">
                        <Plus size={12} className="text-slate-400 shrink-0" />
                        <input
                            value={tagInput}
                            onChange={e => setTagInput(e.target.value)}
                            onKeyDown={handleTagInputKey}
                            onBlur={() => { if (tagInput.trim()) { addTags([tagInput]); setTagInput(''); } }}
                            placeholder="добавить тег + Enter"
                            className="flex-1 text-xs bg-transparent outline-none dark:text-slate-200 placeholder:text-slate-400 py-0.5"
                        />
                    </div>
                </div>
            </div>

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
                                <div className="flex items-center gap-1.5">
                                    {key === 'scoring' && (
                                        <button
                                            onClick={generateScoring}
                                            disabled={generatingScoring || !sessionId}
                                            title={sessionId ? 'Сгенерировать систему оценивания (подзадачи)' : 'Нет активной сессии'}
                                            className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-lg
                                                       bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400
                                                       hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-all disabled:opacity-50"
                                        >
                                            {generatingScoring ? <Loader2 size={10} className="animate-spin" /> : <Sparkles size={10} />}
                                            Сгенерировать
                                        </button>
                                    )}
                                    {canPreview && (value || isEditing) && (
                                        <button
                                            onMouseDown={e => e.preventDefault()} // don't blur the textarea before the click lands
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
                            </div>

                            {showPreview ? (
                                <div
                                    // mousedown (not click): fires before the active textarea blurs,
                                    // so the layout shift from leaving edit mode can't swallow the click
                                    onMouseDown={e => { e.preventDefault(); handleActivate(key); }}
                                    title="Нажмите для редактирования"
                                    className="cursor-text min-h-[44px] text-sm bg-slate-50 dark:bg-slate-800/50
                                               border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2
                                               prose prose-sm dark:prose-invert max-w-none dark:text-slate-200
                                               prose-p:my-1 prose-pre:bg-slate-100 dark:prose-pre:bg-slate-800
                                               break-words overflow-x-auto
                                               [&_p]:break-words [&_pre]:whitespace-pre-wrap [&_pre]:break-words
                                               [&_table]:block [&_table]:w-max [&_table]:max-w-full [&_table]:overflow-x-auto
                                               [&_.katex-display]:overflow-x-auto [&_.katex-display]:overflow-y-hidden"
                                >
                                    <ReactMarkdown
                                        remarkPlugins={[remarkMath, remarkGfm]}
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
                                        onBlur={() => canPreview ? handleDeactivate() : bgSave(statements, activeLang)}
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
                                    onMouseDown={e => { e.preventDefault(); handleActivate(key); }}
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
