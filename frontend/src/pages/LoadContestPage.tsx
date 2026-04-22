import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    CloudDownload, ArrowLeft, Loader2, Info,
    UserCog, Users, Hash, Layers
} from 'lucide-react';
import { api } from '../api/instance';

export const LoadContestPage = () => {
    const navigate = useNavigate();
    const [platform, setPlatform] = useState<'cf' | 'yandex'>('cf');
    const [isLoading, setIsLoading] = useState(false);

    const [formData, setFormData] = useState({
        contest_id: '',
        as_manager: true,
        from_pos: 1,
        count: 100,
        show_unofficial: true
    });

    const handleSync = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            const endpoint = platform === 'cf' ? '/codeforces/standings' : '/yandex/standings';

            await api.post(endpoint, {
                contest_id: parseInt(formData.contest_id),
                as_manager: formData.as_manager,
                from_pos: formData.from_pos,
                count: formData.count,
                show_unofficial: formData.show_unofficial
            });

            alert('Контест успешно загружен!');
            navigate('/contests');
        } catch (err: any) {
            alert('Ошибка при загрузке: ' + (err.response?.data?.detail || 'Проверьте данные и права доступа'));
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto space-y-8 animate-in slide-in-from-bottom-4 duration-500 pb-12">
            <button
                onClick={() => navigate('/contests')}
                className="flex items-center gap-2 text-slate-500 hover:text-blue-600 transition-colors font-medium"
            >
                <ArrowLeft size={20} />
                <span>Назад к списку</span>
            </button>

            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-100 dark:border-slate-800 p-8 shadow-sm">
                <div className="flex items-center gap-4 mb-8">
                    <div className="p-3 bg-blue-600 rounded-2xl text-white">
                        <CloudDownload size={28} />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold dark:text-white">Загрузка данных</h1>
                        <p className="text-slate-500 text-sm">Импорт таблиц из внешних систем.</p>
                    </div>
                </div>

                <form onSubmit={handleSync} className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                        <button
                            type="button"
                            onClick={() => setPlatform('cf')}
                            className={`p-4 rounded-2xl border-2 transition-all text-center ${platform === 'cf' ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-900/20' : 'border-transparent bg-slate-50 dark:bg-slate-800'}`}
                        >
                            <span className="block font-bold dark:text-white">Codeforces</span>
                            <span className="text-xs text-slate-500 italic">API Key / Secret</span>
                        </button>
                        <button
                            type="button"
                            onClick={() => setPlatform('yandex')}
                            className={`p-4 rounded-2xl border-2 transition-all text-center ${platform === 'yandex' ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-900/20' : 'border-transparent bg-slate-50 dark:bg-slate-800'}`}
                        >
                            <span className="block font-bold dark:text-white">Yandex</span>
                            <span className="text-xs text-slate-500 italic">OAuth Token</span>
                        </button>
                    </div>

                    <div>
                        <label className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-300 mb-2 ml-1">
                            <Hash size={16} className="text-blue-600" />
                            ID Контеста
                        </label>
                        <input
                            type="text"
                            required
                            placeholder="Например: 123456"
                            className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-2xl p-4 outline-none focus:ring-2 focus:ring-blue-500 dark:text-white transition-all"
                            value={formData.contest_id}
                            onChange={(e) => setFormData({...formData, contest_id: e.target.value})}
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-6">
                        <div>
                            <label className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-300 mb-2 ml-1">
                                <Layers size={16} className="text-blue-600" />
                                Начиная с позиции
                            </label>
                            <input
                                type="number"
                                min="1"
                                className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-2xl p-4 outline-none focus:ring-2 focus:ring-blue-500 dark:text-white transition-all"
                                value={formData.from_pos}
                                onChange={(e) => setFormData({...formData, from_pos: parseInt(e.target.value)})}
                            />
                        </div>
                        <div>
                            <label className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-300 mb-2 ml-1">
                                <Users size={16} className="text-blue-600" />
                                Количество строк
                            </label>
                            <input
                                type="number"
                                min="1"
                                max="10000"
                                className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-2xl p-4 outline-none focus:ring-2 focus:ring-blue-500 dark:text-white transition-all"
                                value={formData.count}
                                onChange={(e) => setFormData({...formData, count: parseInt(e.target.value)})}
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 gap-4">
                        <label className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-2xl cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors">
                            <div className="flex items-center gap-3">
                                <UserCog size={20} className="text-blue-600" />
                                <div>
                                    <p className="font-bold text-sm dark:text-white">Режим менеджера</p>
                                    <p className="text-xs text-slate-500">Доступ к кодам и расширенным данным</p>
                                </div>
                            </div>
                            <input
                                type="checkbox"
                                className="w-5 h-5 rounded border-none bg-slate-200 dark:bg-slate-600 text-blue-600 focus:ring-0"
                                checked={formData.as_manager}
                                onChange={(e) => setFormData({...formData, as_manager: e.target.checked})}
                            />
                        </label>

                        <label className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-2xl cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors">
                            <div className="flex items-center gap-3">
                                <Users size={20} className="text-blue-600" />
                                <div>
                                    <p className="font-bold text-sm dark:text-white">Вне конкурса</p>
                                    <p className="text-xs text-slate-500">Показывать неофициальных участников</p>
                                </div>
                            </div>
                            <input
                                type="checkbox"
                                className="w-5 h-5 rounded border-none bg-slate-200 dark:bg-slate-600 text-blue-600 focus:ring-0"
                                checked={formData.show_unofficial}
                                onChange={(e) => setFormData({...formData, show_unofficial: e.target.checked})}
                            />
                        </label>
                    </div>

                    <div className="bg-amber-50 dark:bg-amber-900/20 p-4 rounded-2xl flex gap-3 text-amber-700 dark:text-amber-500 text-sm">
                        <Info className="shrink-0" size={20} />
                        <p>Для загрузки результатов приватных тренировок на Codeforces <b>обязательно</b> включите режим менеджера.</p>
                    </div>

                    <button
                        type="submit"
                        disabled={isLoading || !formData.contest_id}
                        className="w-full bg-blue-600 text-white py-4 rounded-2xl font-bold hover:bg-blue-700 disabled:opacity-50 transition-all flex justify-center items-center gap-2 shadow-lg shadow-blue-500/20"
                    >
                        {isLoading ? <Loader2 className="animate-spin" /> : <CloudDownload size={20} />}
                        <span>{isLoading ? 'Импорт данных...' : 'Начать импорт'}</span>
                    </button>
                </form>
            </div>
        </div>
    );
};
