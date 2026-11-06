// components/integrations/ApiTokensIntegration.tsx
//
// Profile card "Токены API (для NlogN)": personal access tokens for the public
// API (/api/public/v1). The NlogN admin stores such a token to list this user's
// problems and import them. A token is shown once; only its hash is kept.

import { useEffect, useState } from 'react';
import { AlertCircle, Check, Copy, KeyRound, Loader2, Trash2 } from 'lucide-react';
import { api } from '../../api/instance';
import { errorText } from '../../api/ai';
import { parseServerDate } from '../../utils/date';

interface ApiToken {
    id: number;
    name: string;
    hint: string;
    created_at: string | null;
    last_used_at: string | null;
}

const formatDate = (s: string | null) => s
    ? parseServerDate(s).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'ещё не использовался';

export const ApiTokensIntegration = () => {
    const [tokens, setTokens] = useState<ApiToken[]>([]);
    const [open, setOpen] = useState(false);
    const [name, setName] = useState('NlogN');
    const [created, setCreated] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = () => api.get<{ tokens: ApiToken[] }>('/integrations/tokens')
        .then(r => setTokens(r.data.tokens)).catch(() => setTokens([]));

    useEffect(() => { load(); }, []);

    const create = async () => {
        setSaving(true);
        setError(null);
        try {
            const res = await api.post<ApiToken & { token: string }>('/integrations/tokens', { name: name.trim() });
            setCreated(res.data.token);
            await load();
        } catch (e) {
            setError(errorText(e, 'Не удалось создать токен'));
        } finally {
            setSaving(false);
        }
    };

    const revoke = async (t: ApiToken) => {
        if (!confirm(`Отозвать токен «${t.name}»? Система, которая им пользуется, потеряет доступ.`)) return;
        try {
            setTokens((await api.delete<{ tokens: ApiToken[] }>(`/integrations/tokens/${t.id}`)).data.tokens);
        } catch (e) {
            alert(errorText(e, 'Ошибка'));
        }
    };

    const copy = async () => {
        if (!created) return;
        try {
            await navigator.clipboard.writeText(created);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // clipboard may be unavailable (http); the token is selectable anyway
        }
    };

    const close = () => {
        setOpen(false);
        setCreated(null);
        setError(null);
    };

    return (
        <>
            <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                <div className="flex justify-between items-center mb-2">
                    <span className="font-bold dark:text-white">Токены API (для NlogN)</span>
                    <span className="text-[10px] bg-slate-200 text-slate-500 px-2 py-1 rounded-full uppercase">
                        {tokens.length ? `${tokens.length} шт.` : 'Нет'}
                    </span>
                </div>
                {tokens.length ? (
                    <ul className="space-y-1 mb-3">
                        {tokens.map(t => (
                            <li key={t.id} className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                                <KeyRound size={12} className="text-slate-400 shrink-0"/>
                                <span className="font-bold truncate">{t.name}</span>
                                <span className="font-mono text-slate-400">{t.hint}</span>
                                <span className="text-slate-400 hidden sm:inline" title="Последнее использование">
                                    · {formatDate(t.last_used_at)}
                                </span>
                                <button onClick={() => revoke(t)} title="Отозвать"
                                        className="ml-auto text-red-500 hover:text-red-600 shrink-0">
                                    <Trash2 size={12}/>
                                </button>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="text-xs text-slate-500 mb-3">
                        Токен вставляется в админке NlogN (вкладка задач «TaskForge»), чтобы импортировать оттуда ваши задачи.
                    </p>
                )}
                <button onClick={() => setOpen(true)}
                        className="w-full bg-blue-600 text-white py-2 rounded-xl text-sm font-bold hover:bg-blue-700 transition-colors">
                    Создать токен
                </button>
            </div>

            {open && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
                    <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl w-full max-w-md shadow-2xl animate-in zoom-in-95 duration-200">
                        <h3 className="text-xl font-bold mb-2 dark:text-white">Новый токен API</h3>
                        {created ? (
                            <div className="space-y-3">
                                <p className="text-sm text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded-xl p-2.5">
                                    Скопируйте токен сейчас — больше он показан не будет.
                                </p>
                                <div className="flex gap-2 items-center">
                                    <input readOnly value={created} onFocus={e => e.target.select()}
                                           className="flex-1 bg-slate-50 dark:bg-slate-800 rounded-xl p-3 text-xs font-mono dark:text-white outline-none"/>
                                    <button onClick={copy} title="Скопировать"
                                            className="p-3 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                                        {copied ? <Check size={16}/> : <Copy size={16}/>}
                                    </button>
                                </div>
                                <p className="text-xs text-slate-500">
                                    Даёт доступ только к публичному API: список ваших задач и их публикация в ejudge.
                                </p>
                                <button onClick={close}
                                        className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700">
                                    Готово
                                </button>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                <p className="text-sm text-slate-500">
                                    Токен даёт доступ только к публичному API: список ваших задач Polygon и их публикация
                                    в ejudge. Его можно отозвать в любой момент.
                                </p>
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase ml-1">Название</label>
                                    <input value={name} onChange={e => setName(e.target.value)} maxLength={100}
                                           className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 mt-1 text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:text-white"/>
                                </div>
                                {error && (
                                    <div className="p-3 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs flex gap-1.5">
                                        <AlertCircle size={14} className="mt-0.5 shrink-0"/> {error}
                                    </div>
                                )}
                                <button onClick={create} disabled={saving || !name.trim()}
                                        className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 disabled:opacity-50 flex justify-center">
                                    {saving ? <Loader2 className="animate-spin" size={20}/> : 'Создать'}
                                </button>
                                <button onClick={close}
                                        className="w-full text-slate-500 text-sm font-medium hover:text-slate-700 dark:hover:text-slate-300">
                                    Отмена
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </>
    );
};
