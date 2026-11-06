// components/integrations/EjudgeIntegration.tsx
//
// Profile card "Ejudge": the user's own ejudge host for the Polygon -> ejudge
// export. SSH by private key or password, the host key is pinned (SHA256
// fingerprint or a known_hosts line). Secrets are never sent back by the
// backend: leaving a secret field empty keeps the stored one.

import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle, Loader2, PlugZap, Server, Unlink } from 'lucide-react';
import { api } from '../../api/instance';
import { errorText } from '../../api/ai';
import { useAuthStore } from '../../store/useAuthStore';

interface EjudgeStatus {
    linked: boolean;
    server_configured: boolean;
    ssh_host?: string;
    ssh_port?: number;
    ssh_user?: string;
    auth_method?: 'key' | 'password';
    host_key?: string | null;
    insecure_host_key?: boolean;
    judges_dir?: string;
    web_url?: string | null;
    web_login?: string | null;
    has_web_password?: boolean;
    has_key_passphrase?: boolean;
    allowed_contests?: string;
}

interface CheckResult { ok: boolean; error: string | null; host_key_fingerprint: string | null; warnings: string[] }

const EMPTY_FORM = {
    ssh_host: '',
    ssh_port: '22',
    ssh_user: 'ejudge',
    auth_method: 'key' as 'key' | 'password',
    ssh_key: '',
    ssh_key_passphrase: '',
    ssh_password: '',
    host_key: '',
    insecure_host_key: false,
    judges_dir: '/home/judges',
    web_url: '',
    web_login: '',
    web_password: '',
    allowed_contests: '',
};

const inputCls = 'w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-2.5 mt-1 text-sm outline-none '
    + 'focus:ring-2 focus:ring-blue-500 dark:text-white';
const labelCls = 'text-xs font-bold text-slate-400 ml-1';

export const EjudgeIntegration = () => {
    const [status, setStatus] = useState<EjudgeStatus | null>(null);
    const [open, setOpen] = useState(false);
    const [form, setForm] = useState(EMPTY_FORM);
    const [busy, setBusy] = useState<'test' | 'save' | null>(null);
    const [check, setCheck] = useState<CheckResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const load = async () => {
        try {
            setStatus((await api.get<EjudgeStatus>('/integrations/ejudge')).data);
        } catch (e) {
            setError(errorText(e, 'Не удалось загрузить настройки ejudge'));
        }
    };

    useEffect(() => { load(); }, []);

    const set = <K extends keyof typeof EMPTY_FORM>(key: K, value: (typeof EMPTY_FORM)[K]) => {
        setForm(f => ({ ...f, [key]: value }));
        setCheck(null);
    };

    const openModal = () => {
        setForm(status?.linked ? {
            ...EMPTY_FORM,
            ssh_host: status.ssh_host || '',
            ssh_port: String(status.ssh_port || 22),
            ssh_user: status.ssh_user || 'ejudge',
            auth_method: status.auth_method || 'key',
            host_key: status.host_key || '',
            insecure_host_key: !!status.insecure_host_key,
            judges_dir: status.judges_dir || '/home/judges',
            web_url: status.web_url || '',
            web_login: status.web_login || '',
            allowed_contests: status.allowed_contests || '',
        } : EMPTY_FORM);
        setCheck(null);
        setError(null);
        setOpen(true);
    };

    const body = () => ({
        ...form,
        ssh_port: Number(form.ssh_port) || 22,
        ssh_key: form.ssh_key || null,
        ssh_key_passphrase: form.ssh_key_passphrase || null,
        ssh_password: form.ssh_password || null,
        host_key: form.host_key.trim() || null,
        web_url: form.web_url.trim() || null,
        web_login: form.web_login.trim() || null,
        web_password: form.web_password || null,
    });

    const test = async () => {
        setBusy('test');
        setError(null);
        try {
            setCheck((await api.post<CheckResult>('/integrations/ejudge/test', body())).data);
        } catch (e) {
            setError(errorText(e, 'Проверка не удалась'));
        } finally {
            setBusy(null);
        }
    };

    const save = async () => {
        setBusy('save');
        setError(null);
        try {
            const res = await api.post<EjudgeStatus & { warnings: string[] }>('/integrations/ejudge', body());
            setStatus(res.data);
            await useAuthStore.getState().fetchUser();
            setOpen(false);
            if (res.data.warnings?.length) alert('Ejudge подключён.\n\n' + res.data.warnings.join('\n'));
        } catch (e) {
            setError(errorText(e, 'Не удалось сохранить'));
        } finally {
            setBusy(null);
        }
    };

    const unlink = async () => {
        if (!confirm('Отвязать свой сервер ejudge? Сохранённые ключ и пароли будут удалены.')) return;
        try {
            setStatus((await api.post<EjudgeStatus>('/integrations/ejudge/unlink')).data);
            await useAuthStore.getState().fetchUser();
        } catch (e) {
            alert(errorText(e, 'Ошибка отвязки'));
        }
    };

    const linked = !!status?.linked;
    const keepSecret = linked && status?.auth_method === form.auth_method;

    return (
        <>
            <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                <div className="flex justify-between items-center mb-2">
                    <span className="font-bold dark:text-white">Ejudge</span>
                    {linked ? (
                        <span className="text-[10px] bg-green-100 text-green-700 px-2 py-1 rounded-full uppercase">Связан</span>
                    ) : status?.server_configured ? (
                        <span className="text-[10px] bg-blue-100 text-blue-700 px-2 py-1 rounded-full uppercase">Сервер по умолчанию</span>
                    ) : (
                        <span className="text-[10px] bg-slate-200 text-slate-500 px-2 py-1 rounded-full uppercase">Не привязан</span>
                    )}
                </div>
                <p className="text-xs text-slate-500 mb-3">
                    {linked
                        ? <>Экспорт задач идёт на <b>{status?.ssh_user}@{status?.ssh_host}</b> ({status?.judges_dir})</>
                        : 'Свой сервер ejudge для экспорта задач из Polygon (вкладка «Пакеты» задачи).'}
                </p>
                <div className="flex gap-3 items-center">
                    <button onClick={openModal}
                            className="flex-1 bg-blue-600 text-white py-2 rounded-xl text-sm font-bold hover:bg-blue-700 transition-colors">
                        {linked ? 'Изменить' : 'Подключить ejudge'}
                    </button>
                    {linked && (
                        <button onClick={unlink} className="text-xs text-red-500 flex items-center gap-1 hover:underline">
                            <Unlink size={14}/> Отвязать
                        </button>
                    )}
                </div>
            </div>

            {open && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
                    <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl animate-in zoom-in-95 duration-200">
                        <h3 className="text-xl font-bold mb-1 dark:text-white flex items-center gap-2">
                            <Server size={20} className="text-blue-600"/> Сервер ejudge
                        </h3>
                        <p className="text-sm text-slate-500 mb-4">
                            Подключение по SSH под пользователем, от которого работает ejudge. Секреты хранятся
                            зашифрованными и обратно не показываются.
                        </p>

                        <div className="space-y-3">
                            <div className="grid grid-cols-[1fr_90px] gap-2">
                                <div>
                                    <label className={labelCls}>SSH-ХОСТ</label>
                                    <input className={inputCls} value={form.ssh_host} placeholder="ejudge.example.org"
                                           onChange={e => set('ssh_host', e.target.value)}/>
                                </div>
                                <div>
                                    <label className={labelCls}>ПОРТ</label>
                                    <input className={inputCls} value={form.ssh_port} inputMode="numeric"
                                           onChange={e => set('ssh_port', e.target.value)}/>
                                </div>
                            </div>
                            <div>
                                <label className={labelCls}>ПОЛЬЗОВАТЕЛЬ SSH</label>
                                <input className={inputCls} value={form.ssh_user} onChange={e => set('ssh_user', e.target.value)}/>
                            </div>

                            <div className="flex gap-2">
                                {(['key', 'password'] as const).map(m => (
                                    <button key={m} type="button" onClick={() => set('auth_method', m)}
                                            className={`flex-1 py-2 rounded-xl text-xs font-bold transition-colors ${form.auth_method === m
                                                ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'}`}>
                                        {m === 'key' ? 'Приватный ключ' : 'Пароль'}
                                    </button>
                                ))}
                            </div>
                            {form.auth_method === 'key' ? (
                                <>
                                    <div>
                                        <label className={labelCls}>ПРИВАТНЫЙ КЛЮЧ (OpenSSH / PEM)</label>
                                        <textarea className={`${inputCls} font-mono text-[11px] h-28`} value={form.ssh_key}
                                                  placeholder={keepSecret ? 'сохранён — оставьте пустым, чтобы не менять'
                                                      : '-----BEGIN OPENSSH PRIVATE KEY-----'}
                                                  onChange={e => set('ssh_key', e.target.value)}/>
                                    </div>
                                    <div>
                                        <label className={labelCls}>ПАРОЛЬ КЛЮЧА (если есть)</label>
                                        <input type="password" className={inputCls} value={form.ssh_key_passphrase}
                                               placeholder={keepSecret && status?.has_key_passphrase ? 'сохранён' : ''}
                                               onChange={e => set('ssh_key_passphrase', e.target.value)}/>
                                    </div>
                                </>
                            ) : (
                                <div>
                                    <label className={labelCls}>ПАРОЛЬ SSH</label>
                                    <input type="password" className={inputCls} value={form.ssh_password}
                                           placeholder={keepSecret ? 'сохранён — оставьте пустым, чтобы не менять' : ''}
                                           onChange={e => set('ssh_password', e.target.value)}/>
                                </div>
                            )}

                            <div>
                                <label className={labelCls}>КЛЮЧ ХОСТА (отпечаток SHA256:… или строка known_hosts)</label>
                                <textarea className={`${inputCls} font-mono text-[11px] h-16`} value={form.host_key}
                                          disabled={form.insecure_host_key}
                                          placeholder="SHA256:… — нажмите «Проверить подключение», чтобы увидеть отпечаток сервера"
                                          onChange={e => set('host_key', e.target.value)}/>
                                <label className="flex items-center gap-2 mt-1 ml-1 text-xs text-slate-500">
                                    <input type="checkbox" checked={form.insecure_host_key}
                                           onChange={e => set('insecure_host_key', e.target.checked)}/>
                                    Не проверять ключ хоста (небезопасно)
                                </label>
                            </div>

                            <div>
                                <label className={labelCls}>КАТАЛОГ КОНТЕСТОВ (judges)</label>
                                <input className={inputCls} value={form.judges_dir} onChange={e => set('judges_dir', e.target.value)}/>
                            </div>

                            <details className="rounded-xl bg-slate-50 dark:bg-slate-800/50 p-3" open={!!form.web_url}>
                                <summary className="text-xs font-bold text-slate-500 cursor-pointer">
                                    Веб-интерфейс (перезагрузка конфигурации после экспорта, необязательно)
                                </summary>
                                <div className="space-y-2 mt-2">
                                    <input className={inputCls} value={form.web_url} placeholder="https://ejudge.example.org/cgi-bin"
                                           onChange={e => set('web_url', e.target.value)}/>
                                    <div className="grid grid-cols-2 gap-2">
                                        <input className={inputCls} value={form.web_login} placeholder="логин serve-control"
                                               onChange={e => set('web_login', e.target.value)}/>
                                        <input type="password" className={inputCls} value={form.web_password}
                                               placeholder={linked && status?.has_web_password ? 'пароль сохранён' : 'пароль'}
                                               onChange={e => set('web_password', e.target.value)}/>
                                    </div>
                                </div>
                            </details>

                            <div>
                                <label className={labelCls}>РАЗРЕШЁННЫЕ КОНТЕСТЫ (через запятую, пусто — любые)</label>
                                <input className={inputCls} value={form.allowed_contests} placeholder="1501, 1502"
                                       onChange={e => set('allowed_contests', e.target.value)}/>
                            </div>

                            {check && (
                                <div className={`p-3 rounded-xl text-xs space-y-1 ${check.ok
                                    ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                                    : 'bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400'}`}>
                                    <div className="flex items-start gap-1.5">
                                        {check.ok ? <CheckCircle size={14} className="mt-0.5 shrink-0"/> : <AlertCircle size={14} className="mt-0.5 shrink-0"/>}
                                        <span>{check.ok ? 'Подключение работает' : check.error}</span>
                                    </div>
                                    {check.host_key_fingerprint && (
                                        <button type="button" onClick={() => set('host_key', check.host_key_fingerprint || '')}
                                                className="font-bold underline">
                                            Доверять этому ключу
                                        </button>
                                    )}
                                    {check.warnings.map((w, i) => <p key={i}>• {w}</p>)}
                                </div>
                            )}
                            {error && (
                                <div className="p-3 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs flex gap-1.5">
                                    <AlertCircle size={14} className="mt-0.5 shrink-0"/> {error}
                                </div>
                            )}

                            <div className="flex gap-2">
                                <button onClick={test} disabled={!!busy || !form.ssh_host}
                                        className="flex-1 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 py-3 rounded-xl font-bold text-sm disabled:opacity-50 flex justify-center items-center gap-1.5">
                                    {busy === 'test' ? <Loader2 className="animate-spin" size={16}/> : <PlugZap size={16}/>}
                                    Проверить подключение
                                </button>
                                <button onClick={save} disabled={!!busy || !form.ssh_host}
                                        className="flex-1 bg-blue-600 text-white py-3 rounded-xl font-bold text-sm hover:bg-blue-700 disabled:opacity-50 flex justify-center">
                                    {busy === 'save' ? <Loader2 className="animate-spin" size={18}/> : 'Сохранить'}
                                </button>
                            </div>
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
