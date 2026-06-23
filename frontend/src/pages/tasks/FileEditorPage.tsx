// pages/tasks/FileEditorPage.tsx
// Full-page code editor for a single Polygon file/solution.

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2, AlertCircle, ArrowLeft, Save, FileCode2 } from 'lucide-react';
import { api } from '../../api/instance';
import { CodeEditor } from '../../components/CodeEditor';

type FileSection = 'source' | 'resource' | 'aux' | 'solution';

const SECTION_LABEL: Record<FileSection, string> = {
    solution: 'Решение',
    source:   'Исходный файл',
    resource: 'Ресурс',
    aux:      'Вспомогательный файл',
};

export const SOLUTION_TAGS: { value: string; label: string }[] = [
    { value: 'MA', label: 'MA — главное решение' },
    { value: 'OK', label: 'OK — корректное' },
    { value: 'WA', label: 'WA — неверный ответ' },
    { value: 'PE', label: 'PE — ошибка формата' },
    { value: 'TL', label: 'TL — превышение времени' },
    { value: 'TO', label: 'TO — TL или OK' },
    { value: 'ML', label: 'ML — превышение памяти' },
    { value: 'RE', label: 'RE — ошибка исполнения' },
    { value: 'RJ', label: 'RJ — отклонено' },
];

export const FileEditorPage = () => {
    const { polygonId: polygonIdStr, section: sectionStr, name: nameStr } = useParams<{
        polygonId: string; section: string; name: string;
    }>();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();

    const polygonId = Number(polygonIdStr);
    const section = (sectionStr ?? 'source') as FileSection;
    const name = nameStr ?? '';

    const [content, setContent] = useState('');
    const [savedContent, setSavedContent] = useState('');
    const [tag, setTag] = useState(searchParams.get('tag') || 'OK');
    const [savedTag, setSavedTag] = useState(searchParams.get('tag') || 'OK');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);

    const isDirty = content !== savedContent || (section === 'solution' && tag !== savedTag);

    useEffect(() => {
        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                let text = '';
                if (section === 'solution') {
                    const res = await api.get(`/polygon/problems/${polygonId}/solutions/${encodeURIComponent(name)}/content`);
                    text = res.data.content ?? '';
                } else {
                    const res = await api.get(
                        `/polygon/problems/${polygonId}/files/content`,
                        { params: { type: section, name } }
                    );
                    text = res.data.content ?? '';
                }
                setContent(text);
                setSavedContent(text);
            } catch (e: any) {
                setError(e?.response?.data?.detail || 'Не удалось загрузить файл');
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [polygonId, section, name]);

    const saveRef = useRef<() => void>(() => {});

    const handleSave = useCallback(async () => {
        setSaving(true);
        setError(null);
        try {
            if (section === 'solution') {
                await api.post(`/polygon/problems/${polygonId}/solutions`, {
                    name,
                    content,
                    tag,
                });
                setSavedTag(tag);
            } else {
                await api.post(`/polygon/problems/${polygonId}/files`, {
                    type: section,
                    name,
                    content,
                    check_existing: false,
                });
            }
            setSavedContent(content);
            setSuccessMsg('Сохранено на Polygon');
            setTimeout(() => setSuccessMsg(null), 2500);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка сохранения');
        } finally {
            setSaving(false);
        }
    }, [polygonId, section, name, content, tag]);

    useEffect(() => { saveRef.current = handleSave; }, [handleSave]);

    // Ctrl+S / Cmd+S to save
    useEffect(() => {
        const onKeyDown = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
                e.preventDefault();
                saveRef.current();
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, []);

    const goBack = () => navigate(`/tasks/${polygonId}?tab=files`);

    return (
        <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950 overflow-hidden">
            {/* Header */}
            <div className="shrink-0 flex items-center gap-3 px-4 lg:px-6 py-3 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex-wrap">
                <button
                    onClick={goBack}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold
                               bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300
                               hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
                >
                    <ArrowLeft size={13} />
                    К файлам
                </button>

                <FileCode2 size={16} className="text-slate-400 shrink-0" />
                <span className="font-bold text-sm font-mono dark:text-white truncate">{name}</span>
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500">
                    {SECTION_LABEL[section] ?? section}
                </span>
                {isDirty && (
                    <span className="text-[11px] font-bold text-amber-500">● не сохранено</span>
                )}

                <div className="flex-1" />

                {successMsg && (
                    <span className="text-xs text-green-600 dark:text-green-400 font-bold">{successMsg}</span>
                )}

                {section === 'solution' && (
                    <div className="flex items-center gap-1.5">
                        <label className="text-[10px] font-bold text-slate-500">Тег</label>
                        <select
                            value={tag}
                            onChange={e => setTag(e.target.value)}
                            className="text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                        >
                            {SOLUTION_TAGS.map(t => (
                                <option key={t.value} value={t.value}>{t.label}</option>
                            ))}
                        </select>
                    </div>
                )}

                <button
                    onClick={handleSave}
                    disabled={saving || loading}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold
                               bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50"
                    title="Ctrl+S"
                >
                    {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                    Сохранить
                </button>
            </div>

            {error && (
                <div className="shrink-0 flex items-center gap-2 mx-4 lg:mx-6 mt-3 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-xl text-sm">
                    <AlertCircle size={16} />
                    {error}
                    <button onClick={() => setError(null)} className="ml-auto text-xs underline">Закрыть</button>
                </div>
            )}

            {/* Editor */}
            <div className="flex-1 min-h-0 p-4 lg:p-6 overflow-hidden flex flex-col">
                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 size={28} className="animate-spin text-blue-500" />
                    </div>
                ) : (
                    <CodeEditor
                        value={content}
                        onChange={setContent}
                        fileName={name}
                        height="100%"
                        className="flex-1 min-h-0 [&_.cm-theme]:h-full [&_.cm-editor]:h-full [&_.cm-scroller]:overflow-auto"
                    />
                )}
            </div>
        </div>
    );
};
