import { useNavigate } from 'react-router-dom';
import { Ghost, Home } from 'lucide-react';

export const NotFound = () => {
    const navigate = useNavigate();

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
            <div className="text-center space-y-6">
                <div className="relative inline-block">
                    <div className="absolute inset-0 bg-blue-500 blur-3xl opacity-20 rounded-full"></div>
                    <Ghost size={80} className="text-blue-600 relative mx-auto animate-bounce" />
                </div>
                <div className="space-y-2">
                    <h1 className="text-4xl font-black text-slate-900 dark:text-white">404</h1>
                    <p className="text-slate-500 dark:text-slate-400 max-w-xs mx-auto">
                        Упс! Похоже, такой страницы не существует.
                    </p>
                </div>
                <button
                    onClick={() => navigate('/')}
                    className="flex items-center gap-2 mx-auto bg-blue-600 text-white px-6 py-3 rounded-2xl font-bold hover:bg-blue-700 transition-all shadow-xl shadow-blue-500/20"
                >
                    <Home size={20} />
                    <span>На главную</span>
                </button>
            </div>
        </div>
    );
};