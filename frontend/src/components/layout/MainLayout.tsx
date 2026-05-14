import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import {
    LayoutDashboard, Trophy, Users, User,
    LogOut, ChevronRight, Sparkles, Settings, X,
    Check
} from 'lucide-react';
// Settings, X, Check — используются только в AISettingsPopup (системный промпт)
import { useAuthStore } from '../../store/useAuthStore';
import { ThemeToggle } from '../ThemeToggle';
import { api } from "../../api/instance.ts";
import { useState, useRef, useEffect } from 'react';

export const AI_MODELS = [
    { id: 'anthropic/claude-opus-4.7',       name: 'Claude 4.7 Opus' },
    { id: 'anthropic/claude-opus-4.6-fast',  name: 'Claude 4.6 Fast' },
    { id: 'google/gemini-3.1-pro-preview',   name: 'Gemini 3.1 Pro' },
    { id: 'google/gemini-3-flash-preview',   name: 'Gemini 3 Flash' },
    { id: 'openai/gpt-5.5-pro',              name: 'GPT-5.5 Pro' },
];

// ─── Попап настроек ИИ ──────────────────────────────────────────────────────
// Настройки хранятся в localStorage и читаются в AITasks
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

const AISettingsPopup = ({
                             onClose,
                         }: {
    onClose: () => void;
}) => {
    const { load, save } = useAISettings();
    const [settings, setSettings] = useState<AISettings>(load);
    const popupRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
                onClose();
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, [onClose]);

    const handleSave = () => {
        save(settings);
        onClose();
    };

    return (
        <>
            {/* Оверлей для затемнения фона (опционально) */}
            <div
                className="fixed inset-0 z-[998] bg-black/5"
                onClick={onClose}
            />

            {/* Сам попап */}
            <div
                ref={popupRef}
                className="
                    fixed z-[999]
                    top-14 left-[calc(16rem+2rem)]
                    w-80 bg-white dark:bg-slate-900
                    border border-slate-200 dark:border-slate-700
                    rounded-2xl shadow-2xl p-4
                    animate-in fade-in slide-in-from-top-2 duration-150
                "
                style={{
                    /* 16rem = ширина сайдбара (w-64), + отступ */
                    /* Если нужно точнее — подстройте значение */
                }}
            >
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-black text-sm dark:text-white">Настройки ИИ</h3>
                    <button
                        onClick={onClose}
                        className="text-slate-400 hover:text-slate-700 dark:hover:text-white transition-colors"
                    >
                        <X size={16} />
                    </button>
                </div>

                {/* Модель */}
                <div className="mb-4">
                    <label className="text-[10px] font-bold uppercase text-slate-400 mb-1.5 block">
                        Модель ИИ
                    </label>
                    <select
                        value={settings.model}
                        onChange={e => setSettings(prev => ({ ...prev, model: e.target.value }))}
                        className="
                            w-full bg-slate-50 dark:bg-slate-800
                            border border-slate-200 dark:border-slate-700
                            rounded-xl px-3 py-2 text-sm dark:text-white
                            outline-none focus:border-blue-500 transition-colors
                        "
                    >
                        {AI_MODELS.map(m => (
                            <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                    </select>
                </div>

                {/* Системный промпт */}
                <div className="mb-4">
                    <label className="text-[10px] font-bold uppercase text-slate-400 mb-1.5 block">
                        Системный промпт
                    </label>
                    <textarea
                        value={settings.systemPrompt}
                        onChange={e => setSettings(prev => ({ ...prev, systemPrompt: e.target.value }))}
                        placeholder="Например: Пиши условия в стиле приключений..."
                        rows={5}
                        className="
                            w-full bg-slate-50 dark:bg-slate-800
                            border border-slate-200 dark:border-slate-700
                            rounded-xl px-3 py-2 text-xs dark:text-white
                            outline-none focus:border-blue-500 transition-colors
                            resize-none font-mono
                        "
                    />
                </div>

                <button
                    onClick={handleSave}
                    className="
                        w-full flex items-center justify-center gap-2
                        bg-blue-600 hover:bg-blue-700 text-white
                        px-4 py-2 rounded-xl text-sm font-bold
                        transition-all shadow-lg shadow-blue-500/20
                    "
                >
                    <Check size={14} />
                    Сохранить
                </button>
            </div>
        </>
    );
};

// ─────────────────────────── MainLayout ─────────────────────────────────────

export const MainLayout = () => {
    const location  = useLocation();
    const navigate  = useNavigate();
    const { user, logout } = useAuthStore();


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
        { icon: Sparkles,        label: 'AI Создание',  path: '/ai-tasks', isAi: true },
        { icon: User,            label: 'Профиль',      path: '/profile' },
    ];

    const currentLabel = menuItems.find(i => i.path === location.pathname)?.label || 'Система';

    return (
        <div className="flex h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-300">
            {/* Сайдбар */}
            <aside className="w-64 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col">
                <div className="p-6 flex items-center gap-3 border-b border-slate-100 dark:border-slate-800">
                    <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold shadow-lg">
                        MC
                    </div>
                    <span className="font-bold text-xl dark:text-white tracking-tight">
                        JudgeSystem
                    </span>
                </div>

                <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                    {menuItems.map(item => {
                        const isActive = location.pathname === item.path;
                        return (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`
                                    flex items-center justify-between px-4 py-3 rounded-xl
                                    transition-all group
                                    ${isActive
                                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/30'
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

            {/* Контентная часть */}
            <div className="flex-1 flex flex-col overflow-hidden">
                {/* Хедер */}
                <header className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-8">
                    <div className="flex items-center gap-3">
                        <span className="text-slate-500 dark:text-slate-400 font-medium">
                            {currentLabel}
                        </span>
                    </div>

                    <div className="flex items-center gap-6">
                        <ThemeToggle />
                        <div className="flex items-center gap-3 pl-6 border-l border-slate-200 dark:border-slate-700">
                            <div className="text-right hidden sm:block">
                                <p className="text-sm font-bold dark:text-white">
                                    {user?.login || 'Пользователь'}
                                </p>
                                <p className="text-xs text-slate-500">Online</p>
                            </div>
                            <div className="w-10 h-10 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center border border-slate-200 dark:border-slate-700">
                                <User size={20} className="text-slate-400" />
                            </div>
                        </div>
                    </div>
                </header>

                <main className="flex-1 overflow-y-auto p-8 bg-slate-50 dark:bg-slate-950">
                    <div className="max-w-6xl mx-auto">
                        <Outlet />
                    </div>
                </main>
            </div>
        </div>
    );
};
