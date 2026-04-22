import {Outlet, Link, useLocation, useNavigate} from 'react-router-dom';
import {LayoutDashboard, Trophy, Users, User, LogOut, ChevronRight, Sparkles} from 'lucide-react';
import {useAuthStore} from '../../store/useAuthStore';
import {ThemeToggle} from '../ThemeToggle';
import {api} from "../../api/instance.ts";

export const MainLayout = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const {user, logout} = useAuthStore();

    const handleLogout = async () => {
        const {accessToken, refreshToken, tokenType} = useAuthStore.getState();

        try {
            await api.post('/auth/logout', {
                access_token: accessToken,
                refresh_token: refreshToken,
                token_type: tokenType
            });
        } catch (error) {
        }

        logout();
        navigate('/');
    };

    const menuItems = [
        {icon: LayoutDashboard, label: 'Обзор', path: '/'},
        {icon: Trophy, label: 'Соревнования', path: '/contests'},
        {icon: Users, label: 'Участники', path: '/participants'},
        {icon: Sparkles, label: 'AI Создание', path: '/ai-tasks', isAi: true},
        {icon: User, label: 'Профиль', path: '/profile'},
    ];

    return (
        <div className="flex h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-300">
            <aside
                className="w-64 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col">
                <div className="p-6 flex items-center gap-3 border-b border-slate-100 dark:border-slate-800">
                    <div
                        className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold shadow-lg">MC
                    </div>
                    <span className="font-bold text-xl dark:text-white tracking-tight">JudgeSystem</span>
                </div>

                <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                    {menuItems.map((item) => {
                        const isActive = location.pathname === item.path;
                        return (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`flex items-center justify-between px-4 py-3 rounded-xl transition-all group ${
                                    isActive
                                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/30'
                                        : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white'
                                }`}
                            >
                                <div className="flex items-center gap-3">
                                    <item.icon size={20}/>
                                    <span className="font-medium">{item.label}</span>
                                </div>
                                {isActive && <ChevronRight size={16}/>}
                            </Link>
                        );
                    })}
                </nav>

                <div className="p-4 border-t border-slate-100 dark:border-slate-800">
                    <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 px-4 py-3 w-full text-slate-500 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                    >
                        <LogOut size={20}/>
                        <span className="font-medium">Выйти</span>
                    </button>
                </div>
            </aside>

            <div className="flex-1 flex flex-col overflow-hidden">
                <header
                    className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-8">
                    <div className="text-slate-500 dark:text-slate-400 font-medium">
                        {menuItems.find(i => i.path === location.pathname)?.label || 'Система'}
                    </div>

                    <div className="flex items-center gap-6">
                        <ThemeToggle/>
                        <div className="flex items-center gap-3 pl-6 border-l border-slate-200 dark:border-slate-700">
                            <div className="text-right hidden sm:block">
                                <p className="text-sm font-bold dark:text-white">{user?.login || 'Пользователь'}</p>
                                <p className="text-xs text-slate-500">Online</p>
                            </div>
                            <div
                                className="w-10 h-10 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center border border-slate-200 dark:border-slate-700">
                                <User size={20} className="text-slate-400"/>
                            </div>
                        </div>
                    </div>
                </header>

                {/* Content */}
                <main className="flex-1 overflow-y-auto p-8 bg-slate-50 dark:bg-slate-950">
                    <div className="max-w-6xl mx-auto">
                        <Outlet/>
                    </div>
                </main>
            </div>
        </div>
    );
};