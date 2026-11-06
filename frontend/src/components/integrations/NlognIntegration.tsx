// components/integrations/NlognIntegration.tsx
//
// Profile card "NlogN": the user's contest.nlogn.info admin account. The backend
// signs in once with the login and password and keeps only the NlogN token
// (encrypted); problems are then published there from the task's Packages tab.

import { useEffect, useState } from 'react';
import { AlertCircle, ExternalLink, Loader2 } from 'lucide-react';
import { api } from '../../api/instance';
import { errorText } from '../../api/ai';
import { useAuthStore } from '../../store/useAuthStore';

export interface NlognStatus {
    linked: boolean;
    default_base_url: string;
    base_url?: string;
    username?: string;
    full_name?: string;
}

const inputCls = 'w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 mt-1 text-sm outline-none '
    + 'focus:ring-2 focus:ring-blue-500 dark:text-white';
const labelCls = 'text-xs font-bold text-slate-400 uppercase ml-1';

export const NlognIntegration = () => {
    const [status, setStatus] = useState<NlognStatus | null>(null);
    const [open, setOpen] = useState(false);
    const [baseUrl, setBaseUrl] = useState('');
    const [login, setLogin] = useState('');
    const [password, setPassword] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        api.get<NlognStatus>('/integrations/nlogn').then(r => setStatus(r.data)).catch(() => setStatus(null));
    }, []);

    const openForm = () => {
        setError(null);
        setBaseUrl(status?.base_url || status?.default_base_url || 'https://contest.nlogn.info');
        setLogin(status?.username || '');
        setPassword('');
        setOpen(true);
    };

    const save = async () => {
        setSaving(true);
        setError(null);
        try {
            const res = await api.post<NlognStatus>('/integrations/nlogn',
                { base_url: baseUrl.trim(), login: login.trim(), password });
            setStatus(res.data);
            setPassword('');
            setOpen(false);
            await useAuthStore.getState().fetchUser();
        } catch (e) {
            setError(errorText(e, 'Не удалось подключить NlogN'));
        } finally {
            setSaving(false);
        }
    };

    const unlink = async () => {
        if (!confirm('Отвязать NlogN? Публиковать задачи туда станет нельзя, пока не привяжете снова.')) return;
        try {
            setStatus((await api.post<NlognStatus>('/integrations/nlogn/unlink')).data);
            await useAuthStore.getState().fetchUser();
        } catch (e) {
            alert(errorText(e, 'Ошибка'));
        }
    };

    return (
        <>
            <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                <div className="flex justify-between items-center mb-2">
                    <span className="font-bold dark:text-white">NlogN</span>
                    {status?.linked ? (
                        <span className="text-[10px] bg-green-100 text-green-700 px-2 py-1 rounded-full uppercase">Связан</span>
                    ) : (
                        <span className="text-[10px] bg-slate-200 text-slate-500 px-2 py-1 rounded-full uppercase">Не привязан</span>
                    )}
                </div>
                {status?.linked ? (
                    <p className="text-xs text-slate-500 mb-3">
                        Публикация задач от имени <b>{status.full_name || status.username}</b> на{' '}
                        <a href={status.base_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline inline-flex items-center gap-0.5">
                            {status.base_url?.replace(/^https?:\/\//, '')} <ExternalLink size={10}/>
                        </a>
                    </p>
                ) : (
                    <p className="text-xs text-slate-500 mb-3">
                        contest.nlogn.info: публикация задач из Polygon (через ejudge) прямо в NlogN, вкладка «Пакеты» задачи.
                    </p>
                )}
                <div className="flex gap-2">
                    <button onClick={openForm}
                            className="flex-1 bg-blue-600 text-white py-2 rounded-xl text-sm font-bold hover:bg-blue-700 transition-colors">
                        {status?.linked ? 'Войти заново' : 'Подключить NlogN'}
                    </button>
                    {status?.linked && (
                        <button onClick={unlink}
                                className="px-3 py-2 rounded-xl text-sm font-bold text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20">
                            Отвязать
                        </button>
                    )}
                </div>
            </div>

            {open && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
                    <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl w-full max-w-md shadow-2xl animate-in zoom-in-95 duration-200">
                        <h3 className="text-xl font-bold mb-2 dark:text-white">Вход в NlogN</h3>
                        <p className="text-sm text-slate-500 mb-4">
                            Нужна учётная запись администратора NlogN. Пароль используется один раз для входа и не
                            сохраняется — хранится только токен NlogN (зашифрованным).
                        </p>
                        <div className="space-y-3">
                            <div>
                                <label className={labelCls}>Адрес NlogN</label>
                                <input className={inputCls} value={baseUrl} onChange={e => setBaseUrl(e.target.value)}
                                       placeholder="https://contest.nlogn.info"/>
                            </div>
                            <div>
                                <label className={labelCls}>Логин или e-mail</label>
                                <input className={inputCls} value={login} autoComplete="username"
                                       onChange={e => setLogin(e.target.value)}/>
                            </div>
                            <div>
                                <label className={labelCls}>Пароль</label>
                                <input type="password" className={inputCls} value={password} autoComplete="current-password"
                                       onChange={e => setPassword(e.target.value)}
                                       onKeyDown={e => { if (e.key === 'Enter' && login && password) save(); }}/>
                            </div>
                            {error && (
                                <div className="p-3 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs flex gap-1.5">
                                    <AlertCircle size={14} className="mt-0.5 shrink-0"/> {error}
                                </div>
                            )}
                            <button onClick={save} disabled={saving || !login.trim() || !password}
                                    className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 disabled:opacity-50 transition-all flex justify-center">
                                {saving ? <Loader2 className="animate-spin" size={20}/> : 'Войти и сохранить'}
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
