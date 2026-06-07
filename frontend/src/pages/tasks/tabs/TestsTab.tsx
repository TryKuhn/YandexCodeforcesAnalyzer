// pages/tasks/tabs/TestsTab.tsx

import { useState, useEffect } from 'react';
import { Loader2, RefreshCw, AlertCircle, ChevronDown, ChevronUp, Eye, Save, X, Clock } from 'lucide-react';
import { api } from '../../../api/instance';

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
    const [tests, setTests] = useState<Test[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Expanded state
    const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
    const [editInputs, setEditInputs] = useState<Record<number, string>>({});
    const [loadingInputs, setLoadingInputs] = useState<Record<number, boolean>>({});
    const [savingIdx, setSavingIdx] = useState<number | null>(null);

    // Answer modal
    const [answerModal, setAnswerModal] = useState<{ index: number; content: string } | null>(null);
    const [loadingAnswer, setLoadingAnswer] = useState<number | null>(null);

    const load = async (showRefreshSpinner = false) => {
        if (showRefreshSpinner) setRefreshing(true);
        else setLoading(true);
        setError(null);
        try {
            // Load without inputs for fast initial list
            const res = await api.get(`/polygon/problems/${polygonId}/tests/tests?no_inputs=true`);
            setTests(res.data || []);
            setEditInputs({});
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка загрузки тестов');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => { load(); }, [polygonId]);

    const fetchInput = async (idx: number) => {
        if (editInputs[idx] !== undefined || loadingInputs[idx]) return;
        setLoadingInputs(prev => ({ ...prev, [idx]: true }));
        try {
            const res = await api.get(
                `/polygon/problems/${polygonId}/tests/tests/${idx}/input`
            );
            const input = res.data.content ?? res.data ?? '';
            setEditInputs(prev => ({ ...prev, [idx]: input }));
            setTests(prev => prev.map(t => t.index === idx ? { ...t, input } : t));
        } catch {
            setEditInputs(prev => ({ ...prev, [idx]: '' }));
        } finally {
            setLoadingInputs(prev => ({ ...prev, [idx]: false }));
        }
    };

    const handleExpand = (idx: number) => {
        const next = expandedIdx === idx ? null : idx;
        setExpandedIdx(next);
        if (next !== null) {
            fetchInput(next);
        }
    };

    const handleSaveInput = async (test: Test) => {
        setSavingIdx(test.index);
        try {
            await api.patch(`/polygon/problems/${polygonId}/tests/tests/${test.index}`, {
                test_input: editInputs[test.index],
            });
            setTests(prev => prev.map(t =>
                t.index === test.index ? { ...t, input: editInputs[test.index] } : t
            ));
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Ошибка сохранения');
        } finally {
            setSavingIdx(null);
        }
    };

    const handleShowAnswer = async (idx: number) => {
        setLoadingAnswer(idx);
        try {
            const res = await api.get(`/polygon/problems/${polygonId}/tests/tests/${idx}/answer`);
            const content = typeof res.data === 'string'
                ? res.data
                : res.data.content ?? res.data.answer ?? JSON.stringify(res.data, null, 2);
            setAnswerModal({ index: idx, content });
        } catch (e: any) {
            setAnswerModal({ index: idx, content: e?.response?.data?.detail || '(ошибка загрузки ответа)' });
        } finally {
            setLoadingAnswer(null);
        }
    };

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

                {tests.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                        <p className="font-bold">Нет тестов</p>
                    </div>
                ) : (
                    <div className="space-y-2">
                        {tests.map(test => {
                            const isExpanded = expandedIdx === test.index;

                            return (
                                <div
                                    key={test.index}
                                    className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden"
                                >
                                    {/* Row header */}
                                    <div
                                        className="flex items-center gap-3 px-3 py-2.5 cursor-pointer
                                                   hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                                        onClick={() => handleExpand(test.index)}
                                    >
                                        <span className="text-xs font-bold text-slate-500 w-6 shrink-0">
                                            #{test.index}
                                        </span>

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

                                        {test.points !== undefined && test.points !== null && (
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

                                        <div className="ml-auto flex items-center gap-1.5 shrink-0">
                                            <button
                                                onClick={e => { e.stopPropagation(); handleShowAnswer(test.index); }}
                                                disabled={loadingAnswer === test.index}
                                                title="Получение ответа занимает ~30 секунд (Polygon вычисляет на лету)"
                                                className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-lg
                                                           bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-blue-500 transition-all"
                                            >
                                                {loadingAnswer === test.index
                                                    ? <><Loader2 size={10} className="animate-spin" /><Clock size={10} className="text-amber-400" /></>
                                                    : <Eye size={10} />
                                                }
                                                Ответ
                                            </button>
                                            {isExpanded
                                                ? <ChevronUp size={14} className="text-slate-400" />
                                                : <ChevronDown size={14} className="text-slate-400" />
                                            }
                                        </div>
                                    </div>

                                    {/* Expanded content */}
                                    {isExpanded && (
                                        <div className="border-t border-slate-200 dark:border-slate-700 p-3">
                                            {loadingInputs[test.index] ? (
                                                <div className="flex items-center gap-2 py-2">
                                                    <Loader2 size={14} className="animate-spin text-blue-500" />
                                                    <span className="text-xs text-slate-400">Загрузка входных данных...</span>
                                                </div>
                                            ) : test.manual ? (
                                                <div className="space-y-2">
                                                    <label className="block text-[10px] font-bold text-slate-500">
                                                        Входные данные (редактируемые)
                                                    </label>
                                                    <textarea
                                                        value={editInputs[test.index] ?? ''}
                                                        onChange={e => setEditInputs(prev => ({ ...prev, [test.index]: e.target.value }))}
                                                        rows={4}
                                                        className="w-full text-xs font-mono bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700
                                                                   rounded-lg px-2 py-2 outline-none dark:text-white resize-y"
                                                    />
                                                    <button
                                                        onClick={() => handleSaveInput(test)}
                                                        disabled={savingIdx === test.index}
                                                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold
                                                                   bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50"
                                                    >
                                                        {savingIdx === test.index
                                                            ? <Loader2 size={12} className="animate-spin" />
                                                            : <Save size={12} />
                                                        }
                                                        Сохранить
                                                    </button>
                                                </div>
                                            ) : (
                                                <div className="space-y-2">
                                                    {test.scriptLine && (
                                                        <div>
                                                            <p className="text-[10px] font-bold text-slate-500 mb-1">Строка генератора</p>
                                                            <pre className="text-xs font-mono text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800 rounded-lg p-2">
                                                                {test.scriptLine}
                                                            </pre>
                                                        </div>
                                                    )}
                                                    {editInputs[test.index] !== undefined && (
                                                        <div>
                                                            <p className="text-[10px] font-bold text-slate-500 mb-1">Сгенерированный ввод (первые 500 символов)</p>
                                                            <pre className="text-xs font-mono text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800 rounded-lg p-2 max-h-32 overflow-y-auto whitespace-pre-wrap">
                                                                {editInputs[test.index]?.slice(0, 500) || '(пусто)'}
                                                            </pre>
                                                        </div>
                                                    )}
                                                    {!editInputs[test.index] && !test.scriptLine && (
                                                        <p className="text-xs text-slate-400 italic">Тест генерируется автоматически</p>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Answer modal */}
            {answerModal && (
                <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl w-full max-w-lg max-h-[70vh] flex flex-col">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800">
                            <span className="font-bold text-sm dark:text-white">Ответ теста #{answerModal.index}</span>
                            <button
                                onClick={() => setAnswerModal(null)}
                                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
                            >
                                <X size={16} />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-4">
                            <pre className="text-xs font-mono text-slate-700 dark:text-slate-200 whitespace-pre-wrap">
                                {answerModal.content}
                            </pre>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};
