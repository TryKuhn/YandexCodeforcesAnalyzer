// pages/tasks/TestViewPage.tsx
// Full-page read-only viewer for a single test's input or output (answer).
// Separate page because test data can be large.

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Loader2, AlertCircle, ArrowLeft, TestTube, Clock, Copy, Check } from 'lucide-react';
import { api } from '../../api/instance';

type Kind = 'input' | 'output';

const KIND_LABEL: Record<Kind, string> = {
    input: 'Входные данные',
    output: 'Ответ жюри',
};

export const TestViewPage = () => {
    const { polygonId: polygonIdStr, index: indexStr, kind: kindStr } = useParams<{
        polygonId: string; index: string; kind: string;
    }>();
    const navigate = useNavigate();

    const polygonId = Number(polygonIdStr);
    const index = Number(indexStr);
    const kind = (kindStr === 'output' ? 'output' : 'input') as Kind;

    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        const extract = (data: any) =>
            typeof data === 'string' ? data : (data?.content ?? data?.answer ?? '');

        const loadInput = async (): Promise<string> => {
            // The test list carries inputs for manual tests — most reliable source.
            try {
                const listRes = await api.get(
                    `/polygon/problems/${polygonId}/tests/tests?no_inputs=false`
                );
                const t = (listRes.data || []).find((x: any) => x.index === index);
                if (t?.input) return t.input;
            } catch { /* fall through to the direct endpoint */ }
            const res = await api.get(`/polygon/problems/${polygonId}/tests/tests/${index}/input`);
            return extract(res.data);
        };

        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                if (kind === 'input') {
                    setContent(await loadInput());
                } else {
                    const res = await api.get(
                        `/polygon/problems/${polygonId}/tests/tests/${index}/answer`
                    );
                    setContent(extract(res.data));
                }
            } catch (e: any) {
                setError(e?.response?.data?.detail || 'Не удалось загрузить данные теста');
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [polygonId, index, kind]);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(content);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        } catch {
            // ignore
        }
    };

    const goBack = () => navigate(`/tasks/${polygonId}?tab=tests`);

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
                    К тестам
                </button>

                <TestTube size={16} className="text-slate-400 shrink-0" />
                <span className="font-bold text-sm dark:text-white">Тест #{index}</span>
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500">
                    {KIND_LABEL[kind]}
                </span>

                <div className="flex-1" />

                <button
                    onClick={handleCopy}
                    disabled={loading || !content}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold
                               bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300
                               hover:bg-slate-200 dark:hover:bg-slate-700 transition-all disabled:opacity-50"
                >
                    {copied ? <Check size={13} className="text-green-500" /> : <Copy size={13} />}
                    {copied ? 'Скопировано' : 'Копировать'}
                </button>
            </div>

            {error && (
                <div className="shrink-0 flex items-center gap-2 mx-4 lg:mx-6 mt-3 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-xl text-sm">
                    <AlertCircle size={16} />
                    {error}
                </div>
            )}

            {/* Content */}
            <div className="flex-1 min-h-0 p-4 lg:p-6 overflow-hidden flex flex-col">
                {loading ? (
                    <div className="flex flex-col items-center justify-center py-20 gap-2">
                        <Loader2 size={28} className="animate-spin text-blue-500" />
                        {kind === 'output' && (
                            <span className="flex items-center gap-1 text-xs text-slate-400">
                                <Clock size={12} className="text-amber-400" />
                                Polygon вычисляет ответ, это может занять ~30 секунд...
                            </span>
                        )}
                    </div>
                ) : (
                    <pre className="flex-1 min-h-0 overflow-auto text-xs font-mono text-slate-700 dark:text-slate-200
                                    bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800
                                    rounded-xl p-4 whitespace-pre">
                        {content || (kind === 'output'
                            ? '(ответ пуст — возможно, тест ещё не вычислен; соберите пакет и убедитесь, что есть основное решение)'
                            : '(пусто)')}
                    </pre>
                )}
            </div>
        </div>
    );
};
