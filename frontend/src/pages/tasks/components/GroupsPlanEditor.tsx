// pages/tasks/components/GroupsPlanEditor.tsx
//
// The test plan: groups (subtasks) with points, dependencies and the generator
// calls of each group. Applying it makes the AI write one generator per group,
// builds the FreeMarker script, assigns tests to groups (COMPLETE_GROUP +
// first-failed, all of a group's points on one test) and rebuilds the package.

import { useEffect, useState } from 'react';
import { Eye, Layers, Loader2, Minus, Plus, Sparkles, Trash2, Wand2 } from 'lucide-react';
import { aiApi, errorText, type AiRun, type PlanGroup, type PlanPreview, type TestPlan } from '../../../api/ai';

interface Props {
    sessionId: string | null;
    disabled?: boolean;
    onRunStarted?: (run: AiRun) => void;
}

const TEMPLATE: TestPlan = {
    use_groups: true,
    groups: [
        { name: '0', samples: true, points: 0, description: 'тесты из условия', dependencies: [], cases: [] },
        {
            name: '1', samples: false, points: 100, description: '', dependencies: ['0'],
            generator: 'gen_1', cases: [{ args: '', count: 5 }],
        },
    ],
};

const input = 'text-[11px] bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md px-1.5 py-1 outline-none dark:text-white';

export const GroupsPlanEditor = ({ sessionId, disabled, onRunStarted }: Props) => {
    const [plan, setPlan] = useState<TestPlan | null>(null);
    const [source, setSource] = useState<string>('');
    const [request, setRequest] = useState('');
    const [preview, setPreview] = useState<PlanPreview | null>(null);
    const [busy, setBusy] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!sessionId) return;
        aiApi.plan(sessionId)
            .then(r => { setPlan(r.plan ?? TEMPLATE); setSource(r.source); })
            .catch(() => setPlan(TEMPLATE));
    }, [sessionId]);

    if (!sessionId || !plan) return null;

    const update = (fn: (p: TestPlan) => TestPlan) => { setPreview(null); setPlan(p => (p ? fn(structuredClone(p)) : p)); };
    const setGroup = (i: number, patch: Partial<PlanGroup>) =>
        update(p => { p.groups[i] = { ...p.groups[i], ...patch }; return p; });
    const total = plan.groups.reduce((s, g) => s + (Number(g.points) || 0), 0);

    const run = async (label: string, fn: () => Promise<void>) => {
        setBusy(label);
        setError(null);
        try { await fn(); } catch (e) { setError(errorText(e, 'Ошибка')); } finally { setBusy(null); }
    };

    const doPreview = () => run('preview', async () => setPreview(await aiApi.previewPlan(sessionId, plan)));
    const apply = () => run('apply', async () => {
        const { run: started } = await aiApi.applyGroups(sessionId, { plan });
        onRunStarted?.(started);
    });
    const fromText = () => run('request', async () => {
        const { run: started } = await aiApi.applyGroups(sessionId, { request });
        onRunStarted?.(started);
        setRequest('');
    });

    return (
        <div className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700">
                <Layers size={14} className="text-slate-400" />
                <span className="text-xs font-bold text-slate-600 dark:text-slate-300 flex-1">
                    Группы тестов и баллы
                    {source === 'polygon' && <span className="font-normal text-slate-400"> (восстановлено из Polygon)</span>}
                </span>
                <label className="flex items-center gap-1 text-[10px] font-bold text-slate-500">
                    <input
                        type="checkbox"
                        checked={plan.use_groups}
                        onChange={e => update(p => ({ ...p, use_groups: e.target.checked }))}
                    />
                    с группами
                </label>
                <span className={`text-[10px] font-bold ${plan.use_groups && total !== 100 ? 'text-amber-500' : 'text-slate-400'}`}>
                    {plan.use_groups ? `Σ ${total}` : ''}
                </span>
            </div>

            <div className="p-3 space-y-2">
                {plan.groups.map((g, i) => (
                    <div key={i} className="rounded-lg border border-slate-100 dark:border-slate-800 p-2 space-y-1.5">
                        <div className="flex flex-wrap items-center gap-1.5">
                            <input className={`${input} w-12`} value={g.name} title="Имя группы"
                                   onChange={e => setGroup(i, { name: e.target.value.trim() })} />
                            {plan.use_groups && (
                                <input className={`${input} w-14`} type="number" min={0} value={g.points} title="Баллы"
                                       onChange={e => setGroup(i, { points: Number(e.target.value) })} />
                            )}
                            <input className={`${input} flex-1 min-w-[140px]`} value={g.description}
                                   placeholder="доп. ограничения, LaTeX: $n \le 10$"
                                   onChange={e => setGroup(i, { description: e.target.value })} />
                            {plan.use_groups && (
                                <input className={`${input} w-20`} value={g.dependencies.join(',')} placeholder="зависит"
                                       title="Группы, без прохождения которых баллы не начисляются (через запятую)"
                                       onChange={e => setGroup(i, {
                                           dependencies: e.target.value.split(',').map(x => x.trim()).filter(Boolean),
                                       })} />
                            )}
                            <label className="flex items-center gap-1 text-[10px] text-slate-500" title="Тесты из условия">
                                <input type="checkbox" checked={g.samples}
                                       onChange={e => setGroup(i, { samples: e.target.checked, points: e.target.checked ? 0 : g.points })} />
                                примеры
                            </label>
                            <button onClick={() => update(p => { p.groups.splice(i, 1); return p; })}
                                    className="text-slate-400 hover:text-red-500" title="Удалить группу">
                                <Trash2 size={12} />
                            </button>
                        </div>
                        {!g.samples && (
                            <div className="pl-2 space-y-1">
                                <div className="flex items-center gap-1.5">
                                    <span className="text-[10px] text-slate-400">генератор</span>
                                    <input className={`${input} w-28 font-mono`} value={g.generator || ''}
                                           onChange={e => setGroup(i, { generator: e.target.value.trim() })} />
                                </div>
                                {g.cases.map((c, j) => (
                                    <div key={j} className="flex items-center gap-1.5">
                                        <span className="text-[10px] font-mono text-slate-400">{g.generator}</span>
                                        <input className={`${input} flex-1 font-mono`} value={c.args} placeholder="аргументы, напр. 10 random"
                                               onChange={e => update(p => { p.groups[i].cases[j].args = e.target.value; return p; })} />
                                        <span className="text-[10px] text-slate-400">×</span>
                                        <input className={`${input} w-12`} type="number" min={1} max={100} value={c.count}
                                               onChange={e => update(p => { p.groups[i].cases[j].count = Number(e.target.value); return p; })} />
                                        <button onClick={() => update(p => { p.groups[i].cases.splice(j, 1); return p; })}
                                                className="text-slate-400 hover:text-red-500"><Minus size={11} /></button>
                                    </div>
                                ))}
                                <button onClick={() => update(p => { p.groups[i].cases.push({ args: '', count: 3 }); return p; })}
                                        className="text-[10px] font-bold text-blue-500 hover:text-blue-700 flex items-center gap-1">
                                    <Plus size={10} /> вызов генератора
                                </button>
                            </div>
                        )}
                    </div>
                ))}
                <button
                    onClick={() => update(p => {
                        const name = String(p.groups.length);
                        p.groups.push({
                            name, samples: false, points: 0, description: '', dependencies: [],
                            generator: `gen_${name}`, cases: [{ args: '', count: 5 }],
                        });
                        return p;
                    })}
                    className="text-[11px] font-bold text-blue-500 hover:text-blue-700 flex items-center gap-1"
                >
                    <Plus size={12} /> группа
                </button>

                {error && <p className="text-[11px] text-red-500 break-words">{error}</p>}

                <div className="flex flex-wrap gap-2 pt-1">
                    <button onClick={doPreview} disabled={!!busy}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold bg-slate-100 dark:bg-slate-800
                                       text-slate-600 dark:text-slate-300 hover:bg-slate-200 disabled:opacity-50">
                        {busy === 'preview' ? <Loader2 size={12} className="animate-spin" /> : <Eye size={12} />} Предпросмотр
                    </button>
                    <button onClick={apply} disabled={!!busy || disabled}
                            title="ИИ напишет генераторы групп, скрипт, расставит группы/баллы и соберёт пакет"
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold bg-blue-600 hover:bg-blue-700
                                       text-white disabled:opacity-50">
                        {busy === 'apply' ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />} Применить план
                    </button>
                </div>

                {preview && (
                    <div className="space-y-1">
                        <p className="text-[11px] text-slate-500">
                            Тестов из скрипта: {preview.tests}{preview.plan.use_groups ? `, сумма баллов ${preview.total_points}` : ''}
                        </p>
                        <pre className="text-[10px] p-2 rounded-lg bg-slate-100 dark:bg-slate-950 overflow-x-auto max-h-48">{preview.script}</pre>
                        {preview.scoring && (
                            <pre className="text-[10px] p-2 rounded-lg bg-slate-100 dark:bg-slate-950 overflow-x-auto max-h-48">{preview.scoring}</pre>
                        )}
                    </div>
                )}

                <div className="border-t border-slate-100 dark:border-slate-800 pt-2 space-y-1.5">
                    <p className="text-[10px] font-bold text-slate-500">Или опишите словами — ИИ составит план сам:</p>
                    <textarea
                        value={request}
                        onChange={e => setRequest(e.target.value)}
                        rows={2}
                        placeholder="Например: 4 подзадачи — n ≤ 10 (15 баллов), n ≤ 1000 (25), все a_i равны (20), без ограничений (40)"
                        className="w-full resize-none text-[11px] bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700
                                   rounded-lg px-2 py-1.5 outline-none dark:text-white"
                    />
                    <button onClick={fromText} disabled={!!busy || disabled || !request.trim()}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold bg-slate-100 dark:bg-slate-800
                                       text-slate-600 dark:text-slate-300 hover:bg-slate-200 disabled:opacity-50">
                        {busy === 'request' ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />} Составить и применить
                    </button>
                </div>
            </div>
        </div>
    );
};
