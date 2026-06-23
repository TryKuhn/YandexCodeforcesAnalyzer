import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { api } from '../api/instance';
import { Key, ArrowLeft, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

export const ChangePassword = () => {
    const { logout } = useAuthStore();
    const navigate = useNavigate();
    const [isChangingPass, setIsChangingPass] = useState(false);
    const [passData, setPassData] = useState({ old: '', new: '', confirm: '' });
    const [status, setStatus] = useState<{ type: string; msg: string }>({ type: '', msg: '' });

    const performLogoutAll = async () => {
        try {
            const refreshToken = useAuthStore.getState().refreshToken;
            await api.post('/auth/logout_all', { refresh_token: refreshToken });
        } catch (e) {
            console.error('Logout all failed', e);
        }
    };

    const handleChangePassword = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsChangingPass(true);
        setStatus({ type: '', msg: '' });

        try {
            await api.post('/auth/change_password', {
                old_password: passData.old,
                new_password: passData.new,
                confirm_password: passData.confirm,
            });

            await performLogoutAll();
            useAuthStore.getState().logout();

            setStatus({ type: 'success', msg: 'Пароль успешно изменён! Перенаправление...' });
            setTimeout(() => {
                logout();
                navigate('/login');
            }, 2000);

            setPassData({ old: '', new: '', confirm: '' });
        } catch (err: any) {
            let errorMessage = 'Произошла ошибка';
            const detail = err.response?.data?.detail;

            if (typeof detail === 'string') {
                errorMessage = detail;
            } else if (Array.isArray(detail)) {
                errorMessage = detail[0]?.msg || 'Ошибка заполнения полей';
            } else if (err.response?.status === 422) {
                errorMessage = 'Данные не соответствуют требованиям';
            }

            setStatus({ type: 'error', msg: errorMessage });
        } finally {
            setIsChangingPass(false);
        }
    };

    return (
        <div className="max-w-md mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <button
                onClick={() => navigate('/profile')}
                className="flex items-center gap-2 text-slate-500 hover:text-blue-600 transition-colors font-medium"
            >
                <ArrowLeft size={20} />
                <span>К профилю</span>
            </button>

            <div className="bg-white dark:bg-slate-900 p-6 sm:p-8 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm">
                <div className="flex items-center gap-3 mb-6 text-slate-900 dark:text-white font-bold text-lg">
                    <div className="p-2.5 bg-blue-600 rounded-xl text-white">
                        <Key size={20} />
                    </div>
                    <span>Смена пароля</span>
                </div>

                <form onSubmit={handleChangePassword} className="space-y-4">
                    <input
                        type="password" placeholder="Текущий пароль"
                        className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none dark:text-white"
                        value={passData.old} onChange={e => setPassData({ ...passData, old: e.target.value })}
                    />
                    <input
                        type="password" placeholder="Новый пароль"
                        className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none dark:text-white"
                        value={passData.new} onChange={e => setPassData({ ...passData, new: e.target.value })}
                    />
                    <input
                        type="password" placeholder="Повторите пароль"
                        className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none dark:text-white"
                        value={passData.confirm} onChange={e => setPassData({ ...passData, confirm: e.target.value })}
                    />

                    {status.msg && (
                        <div className={`text-xs p-3 rounded-lg flex items-center gap-2 ${status.type === 'success' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                            {status.type === 'success' ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                            {status.msg}
                        </div>
                    )}

                    <button
                        disabled={isChangingPass}
                        className="w-full bg-slate-900 dark:bg-white dark:text-slate-900 text-white py-3 rounded-xl font-bold hover:opacity-90 transition-all flex justify-center disabled:opacity-50"
                    >
                        {isChangingPass ? <Loader2 className="animate-spin" size={20} /> : 'Обновить пароль'}
                    </button>

                    <p className="text-xs text-slate-400 text-center">
                        После смены пароля все активные сессии будут закрыты, потребуется повторный вход.
                    </p>
                </form>
            </div>
        </div>
    );
};
