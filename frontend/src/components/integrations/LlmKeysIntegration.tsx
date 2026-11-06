// components/integrations/LlmKeysIntegration.tsx
//
// Profile card "ИИ-модели (свой ключ)": the user's own API keys that the AI
// authoring service uses instead of the server's OpenRouter key. Keys are
// validated by the backend, stored encrypted and shown only as a hint.

import { useEffect, useState } from 'react';
import { AlertCircle, KeyRound, Loader2, Unlink } from 'lucide-react';
import { api } from '../../api/instance';
import { errorText } from '../../api/ai';
import { useAuthStore } from '../../store/useAuthStore';

type Provider = 'openrouter' | 'anthropic' | 'openai';

interface ProviderStatus { linked: boolean; hint: string | null; updated_at: string | null }
interface LlmStatus { providers: Record<Provider, ProviderStatus> }

const PROVIDERS: { id: Provider; name: string; covers: string; placeholder: string }[] = [
    { id: 'anthropic', name: 'Anthropic API', covers: 'модели Claude — напрямую', placeholder: 'sk-ant-api03-…' },
    { id: 'openai', name: 'OpenAI API', covers: 'модели GPT — напрямую', placeholder: 'sk-proj-…' },
    { id: 'openrouter', name: 'OpenRouter', covers: 'все модели', placeholder: 'sk-or-v1-…' },
];

const inputCls = 'w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 mt-1 text-sm outline-none '
    + 'focus:ring-2 focus:ring-blue-500 dark:text-white';

export const LlmKeysIntegration = () => {
    const [status, setStatus] = useState<LlmStatus | null>(null);
    const [open, setOpen] = useState(false);
    const [provider, setProvider] = useState<Provider>('anthropic');
    const [key, setKey] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        api.get<LlmStatus>('/integrations/llm').then(r => setStatus(r.data)).catch(() => setStatus(null));
    }, []);

    const linked = PROVIDERS.filter(p => status?.providers[p.id]?.linked);

    const save = async () => {
        setSaving(true);
        setError(null);
        try {
            setStatus((await api.post<LlmStatus>('/integrations/llm', { provider, api_key: key.trim() })).data);
            await useAuthStore.getState().fetchUser();
            setKey('');
            setOpen(false);
        } catch (e) {
            setError(errorText(e, 'Не удалось сохранить ключ'));
        } finally {
            setSaving(false);
        }
    };

    const unlink = async (p: Provider) => {
        if (!confirm('Удалить сохранённый ключ? ИИ снова будет работать на ключе сервера.')) return;
        try {
            setStatus((await api.post<LlmStatus>(`/integrations/llm/${p}/unlink`)).data);
            await useAuthStore.getState().fetchUser();
        } catch (e) {
            alert(errorText(e, 'Ошибка'));
        }
    };

    return (
        <>
            <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                <div className="flex justify-between items-center mb-2">
                    <span className="font-bold dark:text-white">ИИ-модели (свой ключ)</span>
                    {linked.length ? (
                        <span className="text-[10px] bg-green-100 text-green-700 px-2 py-1 rounded-full uppercase">Свой ключ</span>
                    ) : (
                        <span className="text-[10px] bg-slate-200 text-slate-500 px-2 py-1 rounded-full uppercase">Ключ сервера</span>
                    )}
                </div>
                {linked.length ? (
                    <ul className="space-y-1 mb-3">
                        {linked.map(p => (
                            <li key={p.id} className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                                <KeyRound size={12} className="text-slate-400"/>
                                <span className="font-bold">{p.name}</span>
                                <span className="font-mono text-slate-400">{status?.providers[p.id]?.hint}</span>
                                <button onClick={() => unlink(p.id)} className="ml-auto text-red-500 flex items-center gap-1 hover:underline">
                                    <Unlink size={12}/> Удалить
                                </button>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="text-xs text-slate-500 mb-3">
                        ИИ-создание задач работает на ключе сервера. Можно подключить свой API-ключ.
                    </p>
                )}
                <button onClick={() => { setError(null); setOpen(true); }}
                        className="w-full bg-blue-600 text-white py-2 rounded-xl text-sm font-bold hover:bg-blue-700 transition-colors">
                    {linked.length ? 'Добавить или заменить ключ' : 'Подключить свой ключ'}
                </button>
            </div>

            {open && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
                    <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl w-full max-w-md shadow-2xl animate-in zoom-in-95 duration-200">
                        <h3 className="text-xl font-bold mb-2 dark:text-white">Свой ключ для ИИ</h3>
                        <p className="text-sm text-slate-500 mb-2">
                            Запросы к моделям пойдут на ваш аккаунт: ключ Anthropic — для моделей Claude, ключ
                            OpenAI — для GPT, ключ OpenRouter — для всех остальных. Без ключа используется ключ сервера.
                        </p>
                        <p className="text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded-xl p-2.5 mb-4">
                            Нужен именно API-ключ из консоли разработчика. Подписки Claude Pro/Max и ChatGPT Plus
                            через API не работают.
                        </p>

                        <div className="space-y-3">
                            <div className="flex gap-2">
                                {PROVIDERS.map(p => (
                                    <button key={p.id} type="button" onClick={() => setProvider(p.id)}
                                            className={`flex-1 py-2 rounded-xl text-xs font-bold transition-colors ${provider === p.id
                                                ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'}`}>
                                        {p.name}
                                    </button>
                                ))}
                            </div>
                            <p className="text-[11px] text-slate-400 ml-1">
                                Покрывает: {PROVIDERS.find(p => p.id === provider)?.covers}
                                {status?.providers[provider]?.linked && ` · сейчас сохранён ${status.providers[provider].hint}`}
                            </p>
                            <input type="password" className={inputCls} value={key} autoComplete="off"
                                   placeholder={PROVIDERS.find(p => p.id === provider)?.placeholder}
                                   onChange={e => setKey(e.target.value)}/>

                            {error && (
                                <div className="p-3 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs flex gap-1.5">
                                    <AlertCircle size={14} className="mt-0.5 shrink-0"/> {error}
                                </div>
                            )}

                            <button onClick={save} disabled={saving || key.trim().length < 8}
                                    className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 disabled:opacity-50 transition-all flex justify-center">
                                {saving ? <Loader2 className="animate-spin" size={20}/> : 'Проверить и сохранить'}
                            </button>
                            <button onClick={() => setOpen(false)}
                                    className="w-full text-slate-500 text-sm font-medium hover:text-slate-700 dark:hover:text-slate-300">
                                Отмена
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};
