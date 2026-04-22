import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { api } from '../api/instance';
import { ThemeToggle } from "../components/ThemeToggle.tsx";
import {useAuthStore} from "../store/useAuthStore.ts";

export const RegisterPage = () => {
    const [login, setLogin] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');

    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSuccess, setIsSuccess] = useState(false);

    const navigate = useNavigate();

    const validatePassword = (pass: string) => {
        return {
            length: pass.length >= 8 && pass.length <= 30,
            hasUpper: /[A-Z]/.test(pass),
            hasLower: /[a-z]/.test(pass),
            hasNumber: /[0-9]/.test(pass),
            hasSpecial: /[.,<>_?!@#$%^&*()]/.test(pass)
        };
    };

    const passStatus = validatePassword(password);

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setError('');

        if (password !== confirmPassword) {
            setError('Пароли не совпадают');
            return;
        }

        setIsLoading(true);

        try {
            const response = await api.post('/auth/register', {
                login,
                email,
                password
            });

            const { access_token, refresh_token, token_type } = response.data;

            const setAuth = useAuthStore.getState().setAuthenticated;
            setAuth(access_token, refresh_token, token_type);

            const user_response = await api.get('/auth/me');
            const user = user_response.data;

            const setUser = useAuthStore.getState().setUser;
            setUser(user);

            setIsSuccess(true);
            setTimeout(() => navigate('/'), 1500);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(Array.isArray(detail) ? detail[0].msg : detail || 'Ошибка при регистрации');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen w-full flex flex-col bg-white dark:bg-slate-900 transition-colors duration-300">
            <nav className="w-full border-b border-slate-100 dark:border-slate-800 sticky top-0 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md z-50">
                <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
                    <div className="flex items-center gap-2 font-bold text-2xl text-slate-900 dark:text-white">
                        <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center text-white shadow-lg">MC</div>
                        <span className="hidden sm:inline">Менеджмент контестов</span>
                    </div>
                    <div className="flex items-center gap-6">
                        <ThemeToggle />
                        <Link to="/" className="flex items-center gap-2 font-medium text-slate-600 dark:text-slate-400 hover:text-blue-600 transition-colors">
                            <ArrowLeft size={18} />
                            <span>На главную</span>
                        </Link>
                    </div>
                </div>
            </nav>

            <div className="flex-1 flex items-center justify-center p-6 py-12">
                <div className="bg-slate-50 dark:bg-slate-800 p-8 rounded-2xl shadow-xl border border-slate-100 dark:border-slate-700 w-full max-w-md transition-all">
                    {isSuccess ? (
                        <div className="text-center space-y-4 py-8">
                            <div className="flex justify-center"><CheckCircle2 size={64} className="text-green-500 animate-bounce" /></div>
                            <h2 className="text-2xl font-bold dark:text-white">Успешная регистрация!</h2>
                            <p className="text-slate-500">Перенаправляем вас на главную страницу...</p>
                        </div>
                    ) : (
                        <>
                            <h2 className="text-2xl text-slate-900 dark:text-slate-100 font-bold mb-2 text-center italic">Регистрация</h2>
                            <p className="text-center text-slate-500 dark:text-slate-400 text-sm mb-6">Создайте аккаунт для доступа к системе</p>

                            {error && (
                                <div className="bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 p-3 rounded-lg mb-4 text-sm border border-red-200 dark:border-red-800">
                                    {error}
                                </div>
                            )}

                            <form onSubmit={handleSubmit} className="space-y-4">
                                <div>
                                    <label className="block text-sm dark:text-slate-300 font-medium mb-1 ml-1">Логин</label>
                                    <input
                                        type="text"
                                        className="w-full border border-slate-200 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                                        placeholder="От 5 до 30 символов"
                                        value={login}
                                        onChange={(e) => setLogin(e.target.value)}
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm dark:text-slate-300 font-medium mb-1 ml-1">Email</label>
                                    <input
                                        type="email"
                                        className="w-full border border-slate-200 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                                        placeholder="example@mail.com"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm dark:text-slate-300 font-medium mb-1 ml-1">Пароль</label>
                                    <input
                                        type="password"
                                        className="w-full border border-slate-200 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                                        placeholder="••••••••"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        required
                                    />
                                    <div className="mt-2 grid grid-cols-2 gap-1 text-[10px]">
                                        <PasswordReq label="8-30 знаков" met={passStatus.length} />
                                        <PasswordReq label="A-Z (заглавная)" met={passStatus.hasUpper} />
                                        <PasswordReq label="a-z (строчная)" met={passStatus.hasLower} />
                                        <PasswordReq label="0-9 (цифра)" met={passStatus.hasNumber} />
                                        <PasswordReq label="Спецсимвол" met={passStatus.hasSpecial} />
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-sm dark:text-slate-300 font-medium mb-1 ml-1">Подтвердите пароль</label>
                                    <input
                                        type="password"
                                        className="w-full border border-slate-200 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                                        placeholder="••••••••"
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        required
                                    />
                                </div>

                                <button
                                    type="submit"
                                    disabled={isLoading}
                                    className="w-full bg-blue-600 dark:bg-blue-500 text-white py-3 rounded-lg font-bold hover:bg-blue-700 dark:hover:bg-blue-600 transition-all shadow-lg shadow-blue-500/20 mt-4 flex justify-center items-center gap-2"
                                >
                                    {isLoading ? <Loader2 className="animate-spin" size={20} /> : "Создать аккаунт"}
                                </button>
                            </form>

                            <p className="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
                                Уже есть аккаунт? <Link to="/login" className="text-blue-600 hover:underline font-medium">Войти</Link>
                            </p>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};

const PasswordReq = ({ label, met }: { label: string, met: boolean }) => (
    <div className={`flex items-center gap-1.5 ${met ? 'text-green-500' : 'text-slate-400'}`}>
        {met ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
        <span>{label}</span>
    </div>
);
