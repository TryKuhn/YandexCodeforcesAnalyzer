import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Download, ArrowLeft, Loader2, Info,
    UserCog, Layers, Code2, Database, Hash
} from 'lucide-react';
import { api } from '../api/instance';

export const ImportSubmissions = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [contestInfo, setContestInfo] = useState<any>(null);

    // Общий стейт для всех полей
    const [formData, setFormData] = useState({
        from_pos: 1,
        count: 100,
        as_manager: true,    // Только для CF
        include_source: true // Только для CF
    });

    useEffect(() => {
        api.get(`/contests/${id}/overview`).then(res => {
            setContestInfo(res.data);
        });
    }, [id]);

    const handleImport = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);

        const platform = contestInfo.type; // 'cf' или 'yandex'
        const externalId = parseInt(contestInfo.external_id);

        try {
            let endpoint = '';
            let payload = {};

            if (platform === 'cf') {
                endpoint = '/codeforces/submissions';
                payload = {
                    contest_id: externalId,
                    as_manager: formData.as_manager,
                    from_pos: formData.from_pos,
                    count: formData.count,
                    include_source: formData.include_source
                };
            } else {
                endpoint = '/yandex/submissions';
                payload = {
                    contest_id: externalId,
                    from_pos: formData.from_pos,
                    count: formData.count
                };
            }

            await api.post(endpoint, payload);
            alert('Посылки успешно импортированы!');
            navigate(`/contests/${id}/submissions`);
        } catch (err: any) {
            alert('Ошибка импорта: ' + (err.response?.data?.detail || 'Проверьте настройки API'));
        } finally {
            setLoading(false);
        }
    };

    if (!contestInfo) return null;

    const isCF = contestInfo.type === 'cf';

    return (
        <div className="max-w-2xl mx-auto space-y-6 animate-in slide-in-from-bottom-4 duration-500">
            <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-slate-500 hover:text-blue-600 font-medium">
                <ArrowLeft size={20} /> Назад
            </button>

            <div className="bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm">
                <div className="flex items-center gap-4 mb-8">
                    <div className="p-3 bg-blue-600 rounded-2xl text-white">
                        <Download size={28} />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold dark:text-white">Импорт посылок</h1>
                        <p className="text-slate-500 text-sm">Синхронизация решений для контеста <span className="text-blue-600 font-bold">"{contestInfo.name}"</span></p>
                    </div>
                </div>

                <form onSubmit={handleImport} className="space-y-6">
                    {/* Платформа (выбирается автоматически на основе типа контеста) */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className={`p-4 rounded-2xl border-2 text-center transition-all ${isCF ? 'border-orange-500 bg-orange-50/50 dark:bg-orange-900/10' : 'border-transparent bg-slate-50 dark:bg-slate-800 opacity-50'}`}>
                            <span className={`block font-bold ${isCF ? 'text-orange-600' : 'dark:text-white'}`}>Codeforces</span>
                            <span className="text-[10px] text-slate-500 uppercase">Platform Active</span>
                        </div>
                        <div className={`p-4 rounded-2xl border-2 text-center transition-all ${!isCF ? 'border-red-500 bg-red-50/50 dark:bg-red-900/10' : 'border-transparent bg-slate-50 dark:bg-slate-800 opacity-50'}`}>
                            <span className={`block font-bold ${!isCF ? 'text-red-600' : 'dark:text-white'}`}>Yandex</span>
                            <span className="text-[10px] text-slate-500 uppercase">Platform Active</span>
                        </div>
                    </div>

                    {/* Инфо-плашка с внешним ID */}
                    <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-2xl flex items-center justify-between border border-dashed border-slate-200 dark:border-slate-700">
                        <div className="flex items-center gap-3 text-slate-500 text-sm">
                            <Database size={18} /> <span>Внешний ID контеста</span>
                        </div>
                        <span className="font-mono font-bold text-blue-600">{contestInfo.external_id}</span>
                    </div>

                    {/* Позиция и Количество */}
                    <div className="grid grid-cols-2 gap-6">
                        <div className="space-y-2">
                            <label className="text-sm font-bold text-slate-700 dark:text-slate-300 ml-1 flex items-center gap-2">
                                <Layers size={14} className="text-blue-600" /> Начиная с
                            </label>
                            <input
                                type="number"
                                min="1"
                                className="w-full p-4 bg-slate-50 dark:bg-slate-800 rounded-2xl dark:text-white outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                                value={formData.from_pos}
                                onChange={e => setFormData({...formData, from_pos: parseInt(e.target.value) || 1})}
                            />
                            <p className="text-[10px] text-slate-400 ml-1">Порядковый номер первой посылки</p>
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-bold text-slate-700 dark:text-slate-300 ml-1 flex items-center gap-2">
                                <Hash size={14} className="text-blue-600" /> Количество
                            </label>
                            <input
                                type="number"
                                min="1"
                                max="10000"
                                className="w-full p-4 bg-slate-50 dark:bg-slate-800 rounded-2xl dark:text-white outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                                value={formData.count}
                                onChange={e => setFormData({...formData, count: parseInt(e.target.value) || 1})}
                            />
                            <p className="text-[10px] text-slate-400 ml-1">Лимит запроса (макс 10000)</p>
                        </div>
                    </div>

                    {/* Дополнительные параметры (только для Codeforces) */}
                    {isCF && (
                        <div className="space-y-3 animate-in fade-in slide-in-from-top-2">
                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider ml-1">Настройки Codeforces</h3>

                            <label className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-2xl cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors">
                                <div className="flex items-center gap-3">
                                    <UserCog size={20} className="text-blue-600" />
                                    <div>
                                        <p className="font-bold text-sm dark:text-white">Режим менеджера</p>
                                        <p className="text-[10px] text-slate-500">Доступ к кодам приватных тренировок</p>
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
                                    <Code2 size={20} className="text-emerald-600" />
                                    <div>
                                        <p className="font-bold text-sm dark:text-white">Исходный код</p>
                                        <p className="text-[10px] text-slate-500">Загружать содержимое файлов (Base64)</p>
                                    </div>
                                </div>
                                <input
                                    type="checkbox"
                                    className="w-5 h-5 rounded border-none bg-slate-200 dark:bg-slate-600 text-emerald-600 focus:ring-0"
                                    checked={formData.include_source}
                                    onChange={(e) => setFormData({...formData, include_source: e.target.checked})}
                                />
                            </label>
                        </div>
                    )}

                    <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-2xl flex gap-3 text-blue-700 dark:text-blue-400 text-sm">
                        <Info className="shrink-0" size={20} />
                        <p>Импортированные посылки будут автоматически привязаны к существующим участникам и задачам по их логинам/именам.</p>
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-blue-600 text-white py-4 rounded-2xl font-bold hover:bg-blue-700 disabled:opacity-50 transition-all flex justify-center items-center gap-2 shadow-lg shadow-blue-500/20"
                    >
                        {loading ? <Loader2 className="animate-spin" /> : <Download size={20} />}
                        <span>{loading ? 'Импорт данных...' : 'Начать импорт'}</span>
                    </button>
                </form>
            </div>
        </div>
    );
};
