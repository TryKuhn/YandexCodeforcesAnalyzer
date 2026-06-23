// pages/tasks/tabs/FilesTab.tsx

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, RefreshCw, AlertCircle, Plus, X, FileText, Upload, ChevronRight, DownloadCloud } from 'lucide-react';
import { api } from '../../../api/instance';
import { CodeEditor } from '../../../components/CodeEditor';
import { SOLUTION_TAGS } from '../FileEditorPage';

interface Props {
    polygonId: number;
    sessionId?: string | null;
}

interface PolygonFile {
    name: string;
    size?: number;
    modificationTime?: number;
    type?: string;
    tag?: string;
    sourceType?: string;
}

interface FilesData {
    resourceFiles: PolygonFile[];
    sourceFiles: PolygonFile[];
    auxFiles: PolygonFile[];
    solutions: PolygonFile[];
}

type FileSection = 'source' | 'resource' | 'aux' | 'solution';

const SOLUTION_TAG_BADGE: Record<string, { color: string; bg: string }> = {
    MA: { color: 'text-green-700 dark:text-green-400',  bg: 'bg-green-100 dark:bg-green-900/30' },
    OK: { color: 'text-blue-700 dark:text-blue-400',    bg: 'bg-blue-100 dark:bg-blue-900/30' },
    WA: { color: 'text-red-700 dark:text-red-400',      bg: 'bg-red-100 dark:bg-red-900/30' },
    TL: { color: 'text-yellow-700 dark:text-yellow-400', bg: 'bg-yellow-100 dark:bg-yellow-900/30' },
    ML: { color: 'text-orange-700 dark:text-orange-400', bg: 'bg-orange-100 dark:bg-orange-900/30' },
    RE: { color: 'text-purple-700 dark:text-purple-400', bg: 'bg-purple-100 dark:bg-purple-900/30' },
    RJ: { color: 'text-slate-700 dark:text-slate-400',  bg: 'bg-slate-100 dark:bg-slate-800' },
};

// Role of a "source" file: plain source / checker / validator / generator
const SOURCE_ROLES = [
    { value: 'generic',   label: 'Обычный' },
    { value: 'checker',   label: 'Чекер' },
    { value: 'validator', label: 'Валидатор' },
    { value: 'generator', label: 'Генератор' },
];

const formatSize = (bytes?: number) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
};

// ─── Per-section add form ─────────────────────────────────────────────────────

interface AddFileFormProps {
    polygonId: number;
    section: FileSection;
    onUploaded: () => Promise<void>;
    onClose: () => void;
}

const AddFileForm = ({ polygonId, section, onUploaded, onClose }: AddFileFormProps) => {
    const [name, setName] = useState('');
    const [content, setContent] = useState('');
    const [tag, setTag] = useState('OK');             // solutions only
    const [sourceRole, setSourceRole] = useState('generic'); // source files only
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handlePickFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        try {
            const text = await file.text();
            setContent(text);
            if (!name.trim()) setName(file.name);
        } catch {
            setError('Не удалось прочитать файл');
        }
        e.target.value = '';
    };

    const handleUpload = async () => {
        if (!name.trim()) { setError('Укажите имя файла'); return; }
        setUploading(true);
        setError(null);
        try {
            if (section === 'solution') {
                await api.post(`/polygon/problems/${polygonId}/solutions`, {
                    name: name.trim(),
                    content,
                    tag,
                });
            } else if (section === 'source' && sourceRole === 'checker') {
                await api.post(`/polygon/problems/${polygonId}/checker`, {
                    name: name.trim(),
                    content,
                });
            } else if (section === 'source' && sourceRole === 'validator') {
                await api.post(`/polygon/problems/${polygonId}/validator`, {
                    name: name.trim(),
                    content,
                });
            } else {
                // generic source (incl. generators), resource, aux
                await api.post(`/polygon/problems/${polygonId}/files`, {
                    type: section,
                    name: name.trim(),
                    content,
                });
            }
            await onUploaded();
            onClose();
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка загрузки');
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="border-t border-slate-200 dark:border-slate-700 p-4 space-y-3 bg-slate-50/50 dark:bg-slate-800/20">
            <div className="flex gap-2 flex-wrap">
                <div className="flex-1 min-w-[160px]">
                    <label className="block text-[10px] font-bold text-slate-500 mb-1">Имя файла</label>
                    <input
                        value={name}
                        onChange={e => setName(e.target.value)}
                        placeholder={section === 'solution' ? 'solution.cpp' : 'example.cpp'}
                        className="w-full text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                    />
                </div>

                {section === 'solution' && (
                    <div className="min-w-[180px]">
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Тег решения</label>
                        <select
                            value={tag}
                            onChange={e => setTag(e.target.value)}
                            className="w-full text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                        >
                            {SOLUTION_TAGS.map(t => (
                                <option key={t.value} value={t.value}>{t.label}</option>
                            ))}
                        </select>
                    </div>
                )}

                {section === 'source' && (
                    <div className="min-w-[140px]">
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Тип файла</label>
                        <select
                            value={sourceRole}
                            onChange={e => setSourceRole(e.target.value)}
                            className="w-full text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                        >
                            {SOURCE_ROLES.map(r => (
                                <option key={r.value} value={r.value}>{r.label}</option>
                            ))}
                        </select>
                    </div>
                )}

                <div className="flex items-end">
                    <button
                        onClick={() => fileInputRef.current?.click()}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold
                                   bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300
                                   hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
                    >
                        <Upload size={12} />
                        Выбрать файл
                    </button>
                    <input
                        ref={fileInputRef}
                        type="file"
                        onChange={handlePickFile}
                        className="hidden"
                    />
                </div>
            </div>

            <div>
                <label className="block text-[10px] font-bold text-slate-500 mb-1">Содержимое</label>
                <CodeEditor
                    value={content}
                    onChange={setContent}
                    fileName={name}
                    minHeight="140px"
                    maxHeight="400px"
                    placeholder="// вставьте код или выберите файл..."
                />
            </div>

            {error && <p className="text-xs text-red-500">{error}</p>}

            <div className="flex items-center gap-2">
                <button
                    onClick={handleUpload}
                    disabled={uploading || !name.trim()}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold
                               bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50"
                >
                    {uploading ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
                    Загрузить
                </button>
                <button
                    onClick={onClose}
                    className="px-3 py-2 rounded-xl text-xs font-bold text-slate-500
                               hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
                >
                    Отмена
                </button>
            </div>
        </div>
    );
};

// ─── Files tab ────────────────────────────────────────────────────────────────

export const FilesTab = ({ polygonId, sessionId }: Props) => {
    const navigate = useNavigate();
    const [files, setFiles] = useState<FilesData>({
        resourceFiles: [], sourceFiles: [], auxFiles: [], solutions: []
    });
    const [loading, setLoading] = useState(true);
    const [syncing, setSyncing] = useState(false);
    const [pulling, setPulling] = useState(false);
    const [syncMsg, setSyncMsg] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [addingSection, setAddingSection] = useState<FileSection | null>(null);

    const load = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await api.get(`/polygon/problems/${polygonId}/files`);
            setFiles({
                resourceFiles: res.data.resourceFiles || res.data.resource_files || [],
                sourceFiles:   res.data.sourceFiles   || res.data.source_files   || [],
                auxFiles:      res.data.auxFiles       || res.data.aux_files      || [],
                solutions:     res.data.solutions      || [],
            });
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка загрузки файлов');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, [polygonId]);

    const handleSync = async () => {
        setSyncing(true);
        try { await load(); } finally { setSyncing(false); }
    };

    // Pull statement + all files from Polygon into the AI session.
    const handlePullToSession = async () => {
        if (!sessionId) return;
        setPulling(true);
        setSyncMsg(null);
        setError(null);
        try {
            const res = await api.post(`/ai/session/${sessionId}/sync-from-polygon`);
            setSyncMsg(`Загружено в сессию: ${res.data.files ?? 0} файлов${res.data.statement ? ' + условие' : ''}`);
            await load();
            setTimeout(() => setSyncMsg(null), 4000);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка синхронизации с Polygon');
        } finally {
            setPulling(false);
        }
    };

    const openFile = (f: PolygonFile, section: FileSection) => {
        const params = section === 'solution' && f.tag ? `?tag=${encodeURIComponent(f.tag)}` : '';
        navigate(`/tasks/${polygonId}/files/${section}/${encodeURIComponent(f.name)}${params}`);
    };

    const renderFileRow = (f: PolygonFile, section: FileSection, showTag = false) => (
        <button
            key={f.name}
            onClick={() => openFile(f, section)}
            title="Открыть в редакторе"
            className="w-full flex items-center gap-3 px-3 py-2 hover:bg-blue-50/60 dark:hover:bg-blue-900/10
                       rounded-xl transition-colors group text-left cursor-pointer"
        >
            <FileText size={14} className="text-slate-400 group-hover:text-blue-500 shrink-0 transition-colors" />
            <span className="flex-1 text-sm font-mono text-slate-700 dark:text-slate-200 truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                {f.name}
            </span>
            {showTag && f.tag && (() => {
                const badge = SOLUTION_TAG_BADGE[f.tag] || SOLUTION_TAG_BADGE.RJ;
                return (
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0 ${badge.color} ${badge.bg}`}>
                        {f.tag}
                    </span>
                );
            })()}
            {f.size && (
                <span className="text-[11px] text-slate-400 shrink-0">{formatSize(f.size)}</span>
            )}
            <ChevronRight size={14} className="text-slate-300 dark:text-slate-600 group-hover:text-blue-500 shrink-0 transition-colors" />
        </button>
    );

    const Section = ({
        title, items, section, showTag = false
    }: { title: string; items: PolygonFile[]; section: FileSection; showTag?: boolean }) => {
        const isAdding = addingSection === section;
        return (
            <div className="border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
                <div className="px-4 py-2.5 bg-slate-50 dark:bg-slate-800/50 flex items-center gap-3">
                    <span className="text-xs font-bold text-slate-600 dark:text-slate-300 flex-1">{title}</span>
                    <span className="text-[11px] text-slate-400">{items.length} файлов</span>
                    <button
                        onClick={() => setAddingSection(isAdding ? null : section)}
                        className={`flex items-center gap-1 text-[11px] font-bold px-2 py-1 rounded-lg transition-all
                            ${isAdding
                                ? 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
                                : 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/40'
                            }`}
                    >
                        {isAdding ? <X size={11} /> : <Plus size={11} />}
                        {isAdding ? 'Закрыть' : 'Добавить'}
                    </button>
                </div>
                {items.length === 0 ? (
                    <div className="px-4 py-3 text-xs text-slate-400 italic">Нет файлов</div>
                ) : (
                    <div className="py-1">
                        {items.map(f => renderFileRow(f, section, showTag))}
                    </div>
                )}
                {isAdding && (
                    <AddFileForm
                        polygonId={polygonId}
                        section={section}
                        onUploaded={load}
                        onClose={() => setAddingSection(null)}
                    />
                )}
            </div>
        );
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <Loader2 size={28} className="animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <div className="p-4 lg:p-6 space-y-4 max-w-3xl mx-auto">
            {/* Toolbar */}
            <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-bold text-slate-700 dark:text-slate-200 flex-1">Файлы задачи</span>
                {syncMsg && (
                    <span className="text-xs text-green-600 dark:text-green-400 font-bold">{syncMsg}</span>
                )}
                {sessionId ? (
                    <button
                        onClick={handlePullToSession}
                        disabled={pulling}
                        title="Загрузить условие и все файлы с Polygon в сессию ИИ и обновить список"
                        className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold
                                   bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50
                                   shadow-lg shadow-blue-500/20"
                    >
                        {pulling ? <Loader2 size={13} className="animate-spin" /> : <DownloadCloud size={13} />}
                        Синхронизировать с Polygon
                    </button>
                ) : (
                    <button
                        onClick={handleSync}
                        disabled={syncing}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold
                                   bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300
                                   hover:bg-slate-200 dark:hover:bg-slate-700 transition-all disabled:opacity-50"
                    >
                        {syncing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                        Обновить
                    </button>
                )}
            </div>

            {error && (
                <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-xl text-sm">
                    <AlertCircle size={16} />
                    {error}
                </div>
            )}

            <Section title="Решения"         items={files.solutions}     section="solution" showTag />
            <Section title="Исходные файлы"  items={files.sourceFiles}   section="source" />
            <Section title="Ресурсы"         items={files.resourceFiles} section="resource" />
            <Section title="Вспомогательные" items={files.auxFiles}      section="aux" />
        </div>
    );
};
