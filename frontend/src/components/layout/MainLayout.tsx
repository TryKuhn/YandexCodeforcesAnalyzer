import { useState, useRef, useEffect } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { TaskForgeIcon } from '../TaskForgeLogo';
import {
    Trophy, Users, User, Key,
    LogOut, ChevronDown, Menu, LayoutList, Archive,
} from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { ThemeToggle } from '../ThemeToggle';
import { SiteFooter } from '../SiteFooter';
import { api } from "../../api/instance.ts";

const MENU_ITEMS = [
    { icon: Trophy,     label: 'Соревнования',  path: '/contests' },
    { icon: Users,      label: 'Участники',     path: '/participants' },
    { icon: LayoutList, label: 'Задачи',        path: '/tasks' },
    { icon: Archive,    label: 'Импорт архива', path: '/archive-import' },
];

export const MainLayout = () => {
    const location  = useLocation();
    const navigate  = useNavigate();
    const { user, logout } = useAuthStore();
    const [mobileNavOpen, setMobileNavOpen] = useState(false);
    const [userMenuOpen, setUserMenuOpen] = useState(false);
    const userMenuRef = useRef<HTMLDivElement>(null);

    const fullScreen  = /^\/tasks\/.+/.test(location.pathname);
    // Focused single-purpose pages that shouldn't show the footer.
    const hideFooter  = location.pathname === '/change-password';

    // Close the profile dropdown on any outside click.
    useEffect(() => {
        if (!userMenuOpen) return;
        const onClick = (e: MouseEvent) => {
            if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
                setUserMenuOpen(false);
            }
        };
        document.addEventListener('mousedown', onClick);
        return () => document.removeEventListener('mousedown', onClick);
    }, [userMenuOpen]);

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

    const isActive = (path: string) => location.pathname.startsWith(path);

    const navButtonClass = (active: boolean) => `
        flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-medium transition-all
        ${active
            ? 'bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white shadow-md shadow-violet-500/30'
            : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white'
        }
    `;

    return (
        <div className="flex flex-col h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-300">
            {/* ── Top bar ── */}
            <header className="shrink-0 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
                <div className="h-16 flex items-center justify-between px-4 lg:px-8 gap-4">
                    {/* Left: logo + desktop nav */}
                    <div className="flex items-center gap-3 lg:gap-6 min-w-0">
                        <Link
                            to="/"
                            title="На главную (Обзор)"
                            className="flex items-center gap-2.5 shrink-0 hover:opacity-80 transition-opacity"
                        >
                            <TaskForgeIcon size={30} />
                            <span className="font-bold text-lg dark:text-white tracking-tight hidden sm:inline">
                                TaskForge
                            </span>
                        </Link>

                        <nav className="hidden md:flex items-center gap-1">
                            {MENU_ITEMS.map(item => (
                                <Link key={item.path} to={item.path} className={navButtonClass(isActive(item.path))}>
                                    <item.icon size={18} />
                                    <span>{item.label}</span>
                                </Link>
                            ))}
                        </nav>
                    </div>

                    {/* Right: theme, profile, mobile menu toggle */}
                    <div className="flex items-center gap-2 lg:gap-4">
                        <ThemeToggle />

                        <div className="relative" ref={userMenuRef}>
                            <button
                                onClick={() => setUserMenuOpen(o => !o)}
                                title="Меню профиля"
                                className="flex items-center gap-2 lg:gap-3 lg:pl-4 lg:border-l border-slate-200 dark:border-slate-700 rounded-xl hover:opacity-80 transition-opacity"
                            >
                                <div className="text-right hidden sm:block">
                                    <p className="text-sm font-bold dark:text-white">
                                        {user?.login || 'Пользователь'}
                                    </p>
                                    <p className="text-xs text-slate-500">Online</p>
                                </div>
                                <div className="w-9 h-9 lg:w-10 lg:h-10 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center border border-slate-200 dark:border-slate-700">
                                    <User size={18} className="text-slate-400" />
                                </div>
                                <ChevronDown
                                    size={16}
                                    className={`text-slate-400 transition-transform ${userMenuOpen ? 'rotate-180' : ''}`}
                                />
                            </button>

                            {userMenuOpen && (
                                <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl py-2 z-50 animate-in fade-in zoom-in-95 duration-150">
                                    <div className="px-4 py-2 mb-1 border-b border-slate-100 dark:border-slate-800 sm:hidden">
                                        <p className="text-sm font-bold dark:text-white truncate">
                                            {user?.login || 'Пользователь'}
                                        </p>
                                    </div>
                                    <button
                                        onClick={() => { setUserMenuOpen(false); navigate('/profile'); }}
                                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                                    >
                                        <User size={16} /> Профиль
                                    </button>
                                    <button
                                        onClick={() => { setUserMenuOpen(false); navigate('/change-password'); }}
                                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                                    >
                                        <Key size={16} /> Сменить пароль
                                    </button>
                                    <div className="my-1 border-t border-slate-100 dark:border-slate-800" />
                                    <button
                                        onClick={() => { setUserMenuOpen(false); handleLogout(); }}
                                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                                    >
                                        <LogOut size={16} /> Выйти
                                    </button>
                                </div>
                            )}
                        </div>

                        <button
                            className="md:hidden p-2 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                            onClick={() => setMobileNavOpen(o => !o)}
                            aria-label="Открыть меню"
                        >
                            <Menu size={20} />
                        </button>
                    </div>
                </div>

                {/* Mobile nav dropdown */}
                {mobileNavOpen && (
                    <nav className="md:hidden border-t border-slate-100 dark:border-slate-800 px-4 py-3 space-y-1">
                        {MENU_ITEMS.map(item => (
                            <Link
                                key={item.path}
                                to={item.path}
                                onClick={() => setMobileNavOpen(false)}
                                className={navButtonClass(isActive(item.path)) + ' w-full'}
                            >
                                <item.icon size={18} />
                                <span>{item.label}</span>
                            </Link>
                        ))}
                    </nav>
                )}
            </header>

            {/* ── Content ── */}
            {fullScreen ? (
                // Immersive workspace (task / AI): fixed-height, no page-end footer.
                <main className="flex-1 min-h-0 overflow-hidden bg-slate-50 dark:bg-slate-950">
                    <Outlet />
                </main>
            ) : (
                // Normal pages: footer sits at the end of the content (non-sticky).
                <main className="flex-1 min-h-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 flex flex-col">
                    <div className="flex-1 w-full max-w-6xl mx-auto p-4 lg:p-8">
                        <Outlet />
                    </div>
                    {!hideFooter && <SiteFooter />}
                </main>
            )}
        </div>
    );
};
