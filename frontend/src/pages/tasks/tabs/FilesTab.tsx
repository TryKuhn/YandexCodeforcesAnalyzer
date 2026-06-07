// pages/tasks/tabs/FilesTab.tsx

import { useState, useEffect } from 'react';
import { Loader2, RefreshCw, AlertCircle, Eye, Upload, X, FileText, Edit2, Save } from 'lucide-react';
import { api } from '../../../api/instance';

interface Props {
    polygonId: number;
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

interface ViewState {
    name: string;
    section: FileSection;
    content: string;
    editing: boolean;
    editContent: string;
    saving: boolean;
}

const SOLUTION_TAG_BADGE: Record<string, { color: string; bg: string }> = {
    MA: { color: 'text-green-700 dark:text-green-400',  bg: 'bg-green-100 dark:bg-green-900/30' },
    OK: { color: 'text-blue-700 dark:text-blue-400',    bg: 'bg-blue-100 dark:bg-blue-900/30' },
    WA: { color: 'text-red-700 dark:text-red-400',      bg: 'bg-red-100 dark:bg-red-900/30' },
    TL: { color: 'text-yellow-700 dark:text-yellow-400', bg: 'bg-yellow-100 dark:bg-yellow-900/30' },
    ML: { color: 'text-orange-700 dark:text-orange-400', bg: 'bg-orange-100 dark:bg-orange-900/30' },
    RE: { color: 'text-purple-700 dark:text-purple-400', bg: 'bg-purple-100 dark:bg-purple-900/30' },
    RJ: { color: 'text-slate-700 dark:text-slate-400',  bg: 'bg-slate-100 dark:bg-slate-800' },
};

const formatSize = (bytes?: number) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
};

const FILE_UPLOAD_TYPES = [
    { value: 'resource', label: 'Ресурс' },
    { value: 'source',   label: 'Исходный файл' },
    { value: 'aux',      label: 'Вспомогательный' },
];

export const FilesTab = ({ polygonId }: Props) => {
    const [files, setFiles] = useState<FilesData>({
        resourceFiles: [], sourceFiles: [], auxFiles: [], solutions: []
    });
    const [loading, setLoading] = useState(true);
    const [syncing, setSyncing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [viewState, setViewState] = useState<ViewState | null>(null);
    const [loadingView, setLoadingView] = useState<string | null>(null);

    // Upload form state
    const [uploadType, setUploadType] = useState('resource');
    const [uploadName, setUploadName] = useState('');
    const [uploadContent, setUploadContent] = useState('');
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [uploadSuccess, setUploadSuccess] = useState(false);

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

    const handleView = async (name: string, section: FileSection) => {
        setLoadingView(name);
        try {
            let content = '';
            if (section === 'solution') {
                const res = await api.get(`/polygon/problems/${polygonId}/solutions/${encodeURIComponent(name)}/content`);
                content = res.data.content ?? '';
            } else {
                const res = await api.get(
                    `/polygon/problems/${polygonId}/files/content`,
                    { params: { type: section, name } }
                );
                content = res.data.content ?? '';
            }
            setViewState({ name, section, content, editing: false, editContent: content, saving: false });
        } catch (e: any) {
            setViewState({ name, section, content: `Ошибка: ${e?.response?.data?.detail || 'не удалось загрузить'}`, editing: false, editContent: '', saving: false });
        } finally {
            setLoadingView(null);
        }
    };

    const handleSaveEdit = async () => {
        if (!viewState) return;
        setViewState(v => v ? { ...v, saving: true } : v);
        try {
            if (viewState.section === 'solution') {
                await api.post(`/polygon/problems/${polygonId}/solutions`, {
                    name: viewState.name,
                    content: viewState.editContent,
                });
            } else {
                await api.post(`/polygon/problems/${polygonId}/files`, {
                    type: viewState.section,
                    name: viewState.name,
                    content: viewState.editContent,
                    check_existing: false,
                });
            }
            setViewState(v => v ? { ...v, content: v.editContent, editing: false, saving: false } : v);
        } catch (e: any) {
            setViewState(v => v ? { ...v, saving: false } : v);
            setError(e?.response?.data?.detail || 'Ошибка сохранения');
        }
    };

    const handleUpload = async () => {
        if (!uploadName.trim()) { setUploadError('Укажите имя файла'); return; }
        setUploading(true);
        setUploadError(null);
        try {
            await api.post(`/polygon/problems/${polygonId}/files`, {
                type: uploadType,
                name: uploadName.trim(),
                content: uploadContent,
            });
            setUploadName('');
            setUploadContent('');
            setUploadSuccess(true);
            setTimeout(() => setUploadSuccess(false), 2000);
            await load();
        } catch (e: any) {
            setUploadError(e?.response?.data?.detail || 'Ошибка загрузки');
        } finally {
            setUploading(false);
        }
    };

    const renderFileRow = (f: PolygonFile, section: FileSection, showTag = false) => (
        <div
            key={f.name}
            className="flex items-center gap-3 px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-800/40 rounded-xl transition-colors group"
        >
            <FileText size={14} className="text-slate-400 shrink-0" />
            <span className="flex-1 text-sm font-mono text-slate-700 dark:text-slate-200 truncate">{f.name}</span>
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
            <button
                onClick={() => handleView(f.name, section)}
                disabled={loadingView === f.name}
                className="flex items-center gap-1 text-[11px] font-bold px-2 py-1 rounded-lg
                           bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-blue-500
                           hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all
                           opacity-0 group-hover:opacity-100 disabled:opacity-50 shrink-0"
            >
                {loadingView === f.name ? <Loader2 size={11} className="animate-spin" /> : <Eye size={11} />}
                Открыть
            </button>
        </div>
    );

    const Section = ({
        title, items, section, showTag = false
    }: { title: string; items: PolygonFile[]; section: FileSection; showTag?: boolean }) => (
        <div className="border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
            <div className="px-4 py-2.5 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600 dark:text-slate-300">{title}</span>
                <span className="text-[11px] text-slate-400">{items.length} файлов</span>
            </div>
            {items.length === 0 ? (
                <div className="px-4 py-3 text-xs text-slate-400 italic">Нет файлов</div>
            ) : (
                <div className="py-1">
                    {items.map(f => renderFileRow(f, section, showTag))}
                </div>
            )}
        </div>
    );

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <Loader2 size={28} className="animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <>
            <div className="p-4 lg:p-6 space-y-4 max-w-3xl mx-auto">
                {/* Toolbar */}
                <div className="flex items-center gap-3">
                    <span className="text-sm font-bold text-slate-700 dark:text-slate-200 flex-1">Файлы задачи</span>
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

                {/* Upload form */}
                <div className="border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
                    <div className="px-4 py-2.5 bg-slate-50 dark:bg-slate-800/50 text-xs font-bold text-slate-600 dark:text-slate-300 flex items-center gap-2">
                        <Upload size={13} />
                        Загрузить файл
                    </div>
                    <div className="p-4 space-y-3">
                        <div className="flex gap-2">
                            <div className="flex-1">
                                <label className="block text-[10px] font-bold text-slate-500 mb-1">Тип</label>
                                <select
                                    value={uploadType}
                                    onChange={e => setUploadType(e.target.value)}
                                    className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                                >
                                    {FILE_UPLOAD_TYPES.map(t => (
                                        <option key={t.value} value={t.value}>{t.label}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex-1">
                                <label className="block text-[10px] font-bold text-slate-500 mb-1">Имя файла</label>
                                <input
                                    value={uploadName}
                                    onChange={e => setUploadName(e.target.value)}
                                    placeholder="example.cpp"
                                    className="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 outline-none dark:text-white"
                                />
                            </div>
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 mb-1">Содержимое</label>
                            <textarea
                                value={uploadContent}
                                onChange={e => setUploadContent(e.target.value)}
                                rows={5}
                                placeholder="// код файла..."
                                className="w-full text-xs font-mono bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 outline-none dark:text-white resize-y"
                            />
                        </div>
                        {uploadError && <p className="text-xs text-red-500">{uploadError}</p>}
                        {uploadSuccess && <p className="text-xs text-green-600 dark:text-green-400 font-bold">Файл загружен</p>}
                        <button
                            onClick={handleUpload}
                            disabled={uploading || !uploadName.trim()}
                            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold
                                       bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50"
                        >
                            {uploading ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
                            Загрузить
                        </button>
                    </div>
                </div>
            </div>

            {/* File view/edit modal */}
            {viewState && (
                <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col">
                        {/* Modal header */}
                        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800 shrink-0">
                            <span className="font-bold text-sm dark:text-white font-mono">{viewState.name}</span>
                            <div className="flex items-center gap-2">
                                {viewState.editing ? (
                                    <>
                                        <button
                                            onClick={handleSaveEdit}
                                            disabled={viewState.saving}
                                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50"
                                        >
                                            {viewState.saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                                            Сохранить
                                        </button>
                                        <button
                                            onClick={() => setViewState(v => v ? { ...v, editing: false, editContent: v.content } : v)}
                                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
                                        >
                                            Отмена
                                        </button>
                                    </>
                                ) : (
                                    <button
                                        onClick={() => setViewState(v => v ? { ...v, editing: true, editContent: v.content } : v)}
                                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
                                    >
                                        <Edit2 size={12} />
                                        Редактировать
                                    </button>
                                )}
                                <button
                                    onClick={() => setViewState(null)}
                                    className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
                                >
                                    <X size={16} />
                                </button>
                            </div>
                        </div>
                        {/* Modal content */}
                        <div className="flex-1 overflow-y-auto p-4 min-h-0">
                            {viewState.editing ? (
                                <textarea
                                    value={viewState.editContent}
                                    onChange={e => setViewState(v => v ? { ...v, editContent: e.target.value } : v)}
                                    className="w-full h-full min-h-[400px] text-xs font-mono bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 outline-none dark:text-white resize-none focus:border-blue-500 transition-all"
                                />
                            ) : (
                                <pre className="text-xs font-mono text-slate-700 dark:text-slate-200 whitespace-pre-wrap break-words">
                                    {viewState.content}
                                </pre>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};
