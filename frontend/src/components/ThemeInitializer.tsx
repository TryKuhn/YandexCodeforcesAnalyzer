import { useEffect } from 'react';
import { useThemeStore } from '../store/useThemeStore';

export const ThemeInitializer = () => {
    const { theme } = useThemeStore();

    useEffect(() => {
        const root = window.document.documentElement;

        const isDark =
            theme === 'dark' ||
            (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

        if (isDark) {
            root.classList.add('dark');
        } else {
            root.classList.remove('dark');
        }
    }, [theme]);

    return null;
};
