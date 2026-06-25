// pages/tasks/tabs/TestsTab.tsx

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, RefreshCw, AlertCircle, FileInput, FileOutput, Code2, Edit2, Save, X } from 'lucide-react';
import { api } from '../../../api/instance';
import { CodeEditor } from '../../../components/CodeEditor';

interface Props {
    polygonId: number;
}

interface Test {
    index: number;
    manual: boolean;
    input?: string;
    description?: string;
    useInStatements: boolean;
    scriptLine?: string;
    group?: string;
    points?: number;
}

export const TestsTab = ({ polygonId }: Props) => {
    const navigate = useNavigate();
    const [tests, setTests] = useState<Test[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // FreeMarker generation script
    const [script, setScript] = useState<string>('');
    const [scriptDraft, setScriptDraft] = useState<string>('');
    const [editingScript, setEditingScript] = useState(false);
    const [savingScript, setSavingScript] = useState(false);

    const load = async (showRefreshSpinner = false) => {
        if (showRefreshSpinner) setRefreshing(true);
        else setLoading(true);
        setError(null);
        try {
            const [testsRes, scriptRes] = await Promise.allSettled([
                api.get(`/polygon/problems/${polygonId}/tests/tests?no_inputs=true`),
                api.get(`/polygon/problems/${polygonId}/script/tests`),
            ]);
            if (testsRes.status === 'fulfilled') setTests(testsRes.value.data || []);
            if (scriptRes.status === 'fulfilled') setScript(scriptRes.value.data?.content ?? '');
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка загрузки тестов');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => { load(); }, [polygonId]);

    const startEditScript = () => { setScriptDraft(script); setEditingScript(true); };

    const saveScript = async () => {
        setSavingScript(true);
        try {
            await api.post(`/polygon/problems/${polygonId}/script/tests`, { source: scriptDraft });
            setScript(scriptDraft);
            setEditingScript(false);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка сохранения скрипта');
        } finally {
            setSavingScript(false);
        }
    };

    const viewTest = (index: number, kind: 'input' | 'output') =>
        navigate(`/tasks/${polygonId}/tests/${index}/${kind}`);

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
            <div className="flex items-center gap-3">
                <span className="text-sm font-bold text-slate-700 dark:text-slate-200 flex-1">
                    Тесты ({tests.length})
                </span>
                <button
                    onClick={() => load(true)}
                    disabled={refreshing}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold
                               bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300
                               hover:bg-slate-200 dark:hover:bg-slate-700 transition-all disabled:opacity-50"
                >
                    {refreshing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                    Обновить
                </button>
            </div>

            {error && (
                <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-xl text-sm">
                    <AlertCircle size={16} />
                    {error}
                </div>
            )}

            {/* FreeMarker generation script */}
            <div className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
                <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700">
                    <Code2 size={14} className="text-slate-400" />
                    <span className="text-xs font-bold text-slate-600 dark:text-slate-300 flex-1 min-w-0 truncate">
                        FreeMarker-скрипт генерации тестов
                    </span>
                    {!editingScript ? (
                        <button
                            onClick={startEditScript}
                            className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-lg
                                       bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-blue-500 transition-all"
                        >
                            <Edit2 size={10} /> Редактировать
                        </button>
                    ) : (
                        <div className="flex items-center gap-1">
                            <button
                                onClick={saveScript}
                                disabled={savingScript}
                                className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-lg
                                           bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50"
                            >
                                {savingScript ? <Loader2 size={10} className="animate-spin" /> : <Save size={10} />}
                                Сохранить
                            </button>
                            <button
                                onClick={() => setEditingScript(false)}
                                className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-lg
                                           bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-slate-700 transition-all"
                            >
                                <X size={10} /> Отмена
                            </button>
                        </div>
                    )}
                </div>
                {editingScript ? (
                    <CodeEditor
                        value={scriptDraft}
                        onChange={setScriptDraft}
                        fileName="script.ftl"
                        minHeight="160px"
                        maxHeight="400px"
                        className="!border-0 !rounded-none"
                    />
                ) : script ? (
                    <CodeEditor
                        value={script}
                        readOnly
                        fileName="script.ftl"
                        maxHeight="240px"
                        className="!border-0 !rounded-none"
                    />
                ) : (
                    <p className="text-xs italic text-slate-400 bg-white dark:bg-slate-900 px-3 py-3">
                        (скрипт не задан — тесты заданы вручную или ещё не сгенерированы)
                    </p>
                )}
            </div>

            {/* Tests list */}
            {tests.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                    <p className="font-bold">Нет тестов</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {tests.map(test => (
                        <div
                            key={test.index}
                            className="border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2.5
                                       flex items-center gap-3 flex-wrap"
                        >
                            <span className="text-xs font-bold text-slate-500 w-6 shrink-0">#{test.index}</span>

                            {test.manual ? (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full
                                                 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 shrink-0">
                                    ручной
                                </span>
                            ) : (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full
                                                 bg-slate-100 dark:bg-slate-800 text-slate-500 shrink-0">
                                    генератор
                                </span>
                            )}

                            {test.group && (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full
                                                 bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 shrink-0">
                                    группа {test.group}
                                </span>
                            )}
                            {test.points !== undefined && test.points !== null && test.points > 0 && (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full
                                                 bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 shrink-0">
                                    {test.points} pts
                                </span>
                            )}
                            {test.useInStatements && (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full
                                                 bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 shrink-0">
                                    пример
                                </span>
                            )}

                            {/* Short view: generator command */}
                            {test.scriptLine && (
                                <code className="text-[11px] font-mono text-slate-500 dark:text-slate-400 truncate min-w-0 flex-1">
                                    {test.scriptLine}
                                </code>
                            )}

                            {/* View buttons → separate page */}
                            <div className="ml-auto flex items-center gap-1.5 shrink-0">
                                <button
                                    onClick={() => viewTest(test.index, 'input')}
                                    className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-lg
                                               bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-blue-500 transition-all"
                                >
                                    <FileInput size={11} /> Input
                                </button>
                                <button
                                    onClick={() => viewTest(test.index, 'output')}
                                    title="Polygon вычисляет ответ на лету (~30 сек)"
                                    className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-lg
                                               bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-blue-500 transition-all"
                                >
                                    <FileOutput size={11} /> Output
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
