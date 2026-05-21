import {useState} from 'react';
import {Link, useNavigate} from 'react-router-dom';
import { api } from '../api/instance';
import { useAuthStore } from '../store/useAuthStore';
import {ThemeToggle} from "../components/ThemeToggle.tsx";
import {ArrowLeft} from "lucide-react";
import { TaskForgeIcon } from '../components/TaskForgeLogo';

export const LoginPage = () => {
    const [login, setLogin] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const navigate = useNavigate();
    const setAuth = useAuthStore((state) => state.setAuthenticated);
    const setUser = useAuthStore((state) => state.setUser);

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setError('');

        try {
            const response = await api.post('/auth/login', { login, password });
            const {access_token, refresh_token, token_type} = response.data;

            setAuth(access_token, refresh_token, token_type);

            const user_response = await api.get('/auth/me');
            const user = user_response.data;

            setUser(user);

            navigate('/');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка при входе');
        }
    };

    return (
        <div className="min-h-screen w-full flex flex-col bg-white dark:bg-slate-900 transition-colors duration-300">

            <nav className="w-full border-b border-slate-100 dark:border-slate-800 sticky top-0 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md z-50">
                <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
                    <div className="flex items-center gap-2 font-bold text-2xl text-slate-900 dark:text-white">
                        <TaskForgeIcon size={40} />
                        <span className="hidden sm:inline">TaskForge</span>
                    </div>

                    <div className="flex items-center gap-6">
                        <ThemeToggle />
                        <Link
                            to="/"
                            className="flex items-center gap-2 font-medium text-slate-600 dark:text-slate-400 hover:text-blue-600 transition-colors"
                        >
                            <ArrowLeft size={18} />
                            <span>На главную</span>
                        </Link>
                    </div>
                </div>
            </nav>

            <div className="flex-1 flex items-center justify-center p-6">
                <div className="bg-slate-50 dark:bg-slate-800 p-8 rounded-2xl shadow-xl border border-slate-100 dark:border-slate-700 w-full max-w-md animate-in fade-in zoom-in duration-300">
                    <h2 className="text-2xl text-slate-900 dark:text-slate-100 font-bold mb-6 text-center">
                        Вход в систему
                    </h2>

                    {error && (
                        <div className="bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 p-3 rounded-lg mb-4 text-sm border border-red-200 dark:border-red-800">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label className="block text-sm dark:text-slate-300 font-medium mb-1 ml-1">
                                Логин
                            </label>
                            <input
                                type="text"
                                className="w-full border border-slate-200 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                                placeholder="Введите ваш логин"
                                value={login}
                                onChange={(e) => setLogin(e.target.value)}
                                required
                            />
                        </div>
                        <div>
                            <label className="block text-sm dark:text-slate-300 font-medium mb-1 ml-1">
                                Пароль
                            </label>
                            <input
                                type="password"
                                className="w-full border border-slate-200 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>
                        <button
                            type="submit"
                            className="w-full bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white py-3 rounded-lg font-bold hover:from-violet-700 hover:to-fuchsia-700 transition-all shadow-lg shadow-violet-500/25 mt-2"
                        >
                            Войти
                        </button>
                    </form>

                    <p className="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
                        Нет аккаунта? <Link to="/register" className="text-blue-600 hover:underline font-medium">Создать сейчас</Link>
                    </p>
                </div>
            </div>
        </div>
    );
};