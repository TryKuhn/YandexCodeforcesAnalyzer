import { Link } from 'react-router-dom';

const GITHUB_URL = 'https://github.com/TryKuhn/YandexCodeforcesAnalyzer';

export const SiteFooter = () => (
    <footer className="w-full shrink-0 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-2.5 flex items-center justify-between gap-3 text-xs">
            <p className="text-slate-400 dark:text-slate-500">
                © {new Date().getFullYear()} TaskForge.
            </p>
            <div className="flex gap-4 text-slate-400">
                <Link
                    to="/docs"
                    className="hover:text-violet-600 dark:hover:text-fuchsia-400 transition-colors"
                >
                    Документация
                </Link>
                <a
                    href={GITHUB_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-violet-600 dark:hover:text-fuchsia-400 transition-colors"
                >
                    GitHub
                </a>
            </div>
        </div>
    </footer>
);
