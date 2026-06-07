import { useState } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { TaskForgeIcon } from '../TaskForgeLogo';
import {
    LayoutDashboard, Trophy, Users, User,
    LogOut, ChevronRight, Menu, LayoutList,
} from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { ThemeToggle } from '../ThemeToggle';
import { api } from "../../api/instance.ts";

export const AI_MODELS = [
    { id: 'anthropic/claude-opus-4.7',       name: 'Claude 4.7 Opus' },
    { id: 'anthropic/claude-sonnet-4.6',     name: 'Claude Sonnet 4.6' },
    { id: 'anthropic/claude-opus-4.6-fast',  name: 'Claude 4.6 Fast' },
    { id: 'google/gemini-3.1-pro-preview',   name: 'Gemini 3.1 Pro' },
    { id: 'google/gemini-3-flash-preview',   name: 'Gemini 3 Flash' },
    { id: 'openai/gpt-5.5-pro',              name: 'GPT-5.5 Pro' },
];

const AI_SETTINGS_KEY = 'ai_tasks_settings';

export interface AISettings {
    model: string;
    systemPrompt: string;
}

const DEFAULT_SETTINGS: AISettings = {
    model: AI_MODELS[0].id,
    systemPrompt: '',
};

export const useAISettings = () => {
    const load = (): AISettings => {
        try {
            const raw = localStorage.getItem(AI_SETTINGS_KEY);
            return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : DEFAULT_SETTINGS;
        } catch {
            return DEFAULT_SETTINGS;
        }
    };

    const save = (settings: AISettings) => {
        localStorage.setItem(AI_SETTINGS_KEY, JSON.stringify(settings));
    };

    return { load, save };
};


export const MainLayout = () => {
    const location  = useLocation();
    const navigate  = useNavigate();
    const { user, logout } = useAuthStore();
    const [sidebarOpen, setSidebarOpen] = useState(false);

    const isAISession = /^\/ai-tasks\/.+/.test(location.pathname);
    const isTaskPage  = /^\/tasks\/.+/.test(location.pathname);

    const handleLogout = async () => {
        const { accessToken, refreshToken, tokenType } = useAuthStore.getState();
        try {
            await api.post('/auth/logout', {
                access_token: accessToken,
                refresh_token: refreshToken,
                token_type: tokenType,
            });
        } catch {}
        logout();
        navigate('/');
    };

    const menuItems = [
        { icon: LayoutDashboard, label: 'Обзор',        path: '/' },
        { icon: Trophy,          label: 'Соревнования', path: '/contests' },
        { icon: Users,           label: 'Участники',    path: '/participants' },
        { icon: LayoutList,      label: 'Задачи',       path: '/tasks' },
        { icon: User,            label: 'Профиль',      path: '/profile' },
    ];

    const currentLabel = menuItems.find(i => i.path === location.pathname)?.label || 'Система';

    return (
        <div className="flex h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-300">
            {sidebarOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/40 lg:hidden"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            <aside className={`
                fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col
                transform transition-transform duration-200 ease-in-out
                lg:relative lg:translate-x-0
                ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
            `}>
                <div className="p-6 flex items-center gap-3 border-b border-slate-100 dark:border-slate-800">
                    <TaskForgeIcon size={32} />
                    <span className="font-bold text-xl dark:text-white tracking-tight">
                        TaskForge
                    </span>
                </div>

                <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                    {menuItems.map(item => {
                        const isActive = location.pathname === item.path;
                        return (
                            <Link
                                key={item.path}
                                to={item.path}
                                onClick={() => setSidebarOpen(false)}
                                className={`
                                    flex items-center justify-between px-4 py-3 rounded-xl
                                    transition-all group
                                    ${isActive
                                    ? 'bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white shadow-lg shadow-violet-500/30'
                                    : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white'
                                }
                                `}
                            >
                                <div className="flex items-center gap-3">
                                    <item.icon size={20} />
                                    <span className="font-medium">{item.label}</span>
                                </div>
                                {isActive && <ChevronRight size={16} />}
                            </Link>
                        );
                    })}
                </nav>

                <div className="p-4 border-t border-slate-100 dark:border-slate-800">
                    <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 px-4 py-3 w-full text-slate-500 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                    >
                        <LogOut size={20} />
                        <span className="font-medium">Выйти</span>
                    </button>
                </div>
            </aside>

            <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
                <header className="h-16 shrink-0 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-4 lg:px-8">
                    <div className="flex items-center gap-2 lg:gap-3">
                        <button
                            className="lg:hidden p-2 -ml-1 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                            onClick={() => setSidebarOpen(prev => !prev)}
                            aria-label="Открыть меню"
                        >
                            <Menu size={20} />
                        </button>
                        <span className="text-slate-500 dark:text-slate-400 font-medium text-sm lg:text-base">
                            {currentLabel}
                        </span>
                    </div>

                    <div className="flex items-center gap-3 lg:gap-6">
                        <ThemeToggle />
                        <div className="flex items-center gap-2 lg:gap-3 lg:pl-6 lg:border-l border-slate-200 dark:border-slate-700">
                            <div className="text-right hidden sm:block">
                                <p className="text-sm font-bold dark:text-white">
                                    {user?.login || 'Пользователь'}
                                </p>
                                <p className="text-xs text-slate-500">Online</p>
                            </div>
                            <div className="w-8 h-8 lg:w-10 lg:h-10 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center border border-slate-200 dark:border-slate-700">
                                <User size={18} className="text-slate-400" />
                            </div>
                        </div>
                    </div>
                </header>

                {(isAISession || isTaskPage) ? (
                    <main className="flex-1 overflow-hidden bg-slate-50 dark:bg-slate-950">
                        <Outlet />
                    </main>
                ) : (
                    <main className="flex-1 overflow-y-auto p-4 lg:p-8 bg-slate-50 dark:bg-slate-950">
                        <div className="max-w-6xl mx-auto">
                            <Outlet />
                        </div>
                    </main>
                )}
            </div>
        </div>
    );
};
