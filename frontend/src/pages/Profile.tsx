import {useState, useEffect} from 'react';
import {useAuthStore} from '../store/useAuthStore';
import {api} from '../api/instance';
import {
    User, Key, Shield, Monitor, CheckCircle2, AlertCircle, Loader2, Globe, Unlink, Clock
} from 'lucide-react';
import {useNavigate} from "react-router-dom";

export const Profile = () => {
    const {user, logout} = useAuthStore();
    const navigate = useNavigate();
    const [sessions, setSessions] = useState<any[]>([]);
    const [isChangingPass, setIsChangingPass] = useState(false);
    const [passData, setPassPassData] = useState({old: '', new: '', confirm: ''});
    const [status, setStatus] = useState({type: '', msg: ''});

    {/* CF Legacy */
    }
    const [cfData, setCfData] = useState({key: '', secret: ''});
    const [showCfModal, setShowCfModal] = useState(false);
    const [isLinkingCf, setIsLinkingCf] = useState(false);

    const [polyData, setPolyData] = useState({key: '', secret: ''});
    const [showPolyModal, setShowPolyModal] = useState(false);
    const [isLinkingPoly, setIsLinkingPoly] = useState(false);

    const handleCFLink = async () => {
        setIsLinkingCf(true);
        try {
            await api.post('/codeforces/link', {
                api_key: cfData.key,
                api_secret: cfData.secret
            });
            await useAuthStore.getState().fetchUser();
            setShowCfModal(false);
            setCfData({key: '', secret: ''});
            alert('Codeforces привязан!');
        } catch (e) {
            alert('Ошибка привязки. Проверьте ключи.');
        } finally {
            setIsLinkingCf(false);
        }
    };

    const handleCFUnlink = async () => {
        if (confirm('Отвязать аккаунт Codeforces?')) {
            try {
                await api.post('/codeforces/unlink');
                await useAuthStore.getState().fetchUser();
            } catch (e) {
                console.error(e);
            }
        }
    };

    const handlePolyLink = async () => {
        setIsLinkingPoly(true);
        try {
            await api.post('/polygon/link', {
                api_key: polyData.key,
                api_secret: polyData.secret
            });
            await useAuthStore.getState().fetchUser();
            setShowPolyModal(false);
            setPolyData({key: '', secret: ''});
            alert('Polygon успешно привязан!');
        } catch (e) {
            alert('Ошибка привязки Polygon. Проверьте ключи.');
        } finally {
            setIsLinkingPoly(false);
        }
    };

    const handlePolyUnlink = async () => {
        if (confirm('Отвязать аккаунт Polygon?')) {
            try {
                await api.post('/polygon/unlink');
                await useAuthStore.getState().fetchUser();
            } catch (e) {
                console.error(e);
            }
        }
    };

    // const handleCFStart = async () => {
    //     try {
    //         const res = await api.get('/codeforces/auth_url');
    //         const {url, code_verifier} = res.data;
    //
    //         sessionStorage.setItem('cf_verifier', code_verifier);
    //
    //         window.location.href = url;
    //     } catch (e) {
    //         console.error(e);
    //     }
    // };

    // const handleCFUnlink = async () => {
    //     try {
    //         await api.post('/codeforces/unlink');
    //         await useAuthStore.getState().fetchUser();
    //         alert('Codeforces отвязан!');
    //         window.location.reload();
    //     } catch (e) {
    //         alert('Ошибка отвязки');
    //     }
    // }

    const handleYandexStart = async () => {
        try {
            const res = await api.get('/yandex/auth_url');
            window.location.href = res.data.url;
        } catch (e) {
            console.error(e);
        }
    };

    const handleYandexUnlink = async () => {
        try {
            await api.post('/yandex/logout');
            await useAuthStore.getState().fetchUser();
            alert('Yandex отвязан');
        } catch (e) {
            alert('Ошибка отвязки');
        }
    }

    useEffect(() => {
        fetchSessions();
    }, []);

    const fetchSessions = async () => {
        try {
            const res = await api.get('/auth/sessions');
            setSessions(res.data);
        } catch (e) {
            console.error(e);
        }
    };

    const performLogoutAll = async () => {
        try {
            await api.post('/auth/logout_all');
        } catch (e) {
            console.error("Logout all failed", e);
        }
    };

    const handleLogoutAllManual = async () => {
        if (confirm('Выйти изо всех сессий?')) {
            await performLogoutAll();
            useAuthStore.getState().logout()

            await fetchSessions();
            alert('Все сессии закрыты.');
        }
    };

    const handleChangePassword = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsChangingPass(true);
        setStatus({type: '', msg: ''});

        try {
            await api.post('/auth/change_password', {
                old_password: passData.old,
                new_password: passData.new,
                confirm_password: passData.confirm
            });

            await performLogoutAll();
            useAuthStore.getState().logout()

            setStatus({type: 'success', msg: 'Пароль успешно изменен! Перенаправление...'});
            setTimeout(() => {
                logout();
                navigate('/login');
            }, 2000);

            setPassPassData({old: '', new: '', confirm: ''});
        } catch (err: any) {
            let errorMessage = 'Произошла ошибка';

            const detail = err.response?.data?.detail;

            if (typeof detail === 'string') {
                errorMessage = detail;
            } else if (Array.isArray(detail)) {
                errorMessage = detail[0]?.msg || 'Ошибка заполнения полей';
            } else if (err.response?.status === 422) {
                errorMessage = "Данные не соответствуют требованиям";
            }

            setStatus({type: 'error', msg: errorMessage});
        } finally {
            setIsChangingPass(false);
        }
    };

    const formatSessionInfo = (rawUa: string) => {
        if (!rawUa) return {location: 'Неизвестно', browser: 'Неизвестное устройство'};
        const [location, ...uaParts] = rawUa.split(' | ');
        const ua = uaParts.join(' ');

        const formatUa = (ua: string) => {
            if (!ua) return {device: 'Unknown', browser: 'Browser'};
            const browser = ua.includes('Edg/') ? 'Edge' : ua.includes('OPR') ? 'Opera' : ua.includes('Chrome') ? 'Chrome' : ua.includes('Firefox') ? 'Firefox' : 'Safari';

            let os: string;
            if (ua.includes('Android')) {
                os = 'Android';
            } else if (ua.includes('iPhone') || ua.includes('iPad')) {
                os = 'iOS';
            } else if (ua.includes('Windows')) {
                os = 'Windows';
            } else if (ua.includes('Macintosh') || ua.includes('Mac OS X')) {
                os = 'macOS';
            } else if (ua.includes('Linux')) {
                os = 'Linux';
            } else {
                os = 'Другая ОС';
            }

            return {device: os, browser: browser};
        };

        const {device, browser} = formatUa(ua);

        return {location, device: `${browser} на ${device}`};
    };

    const formatLastSeen = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = Math.floor((now.getTime() - date.getTime()) / 1000);

        if (diff < 60) return 'Только что';
        if (diff < 3600) return `${Math.floor(diff / 60)} мин. назад`;
        if (diff < 86400) return `${Math.floor(diff / 3600)} ч. назад`;

        return date.toLocaleString([], {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    return (
        <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center gap-4">
                <div
                    className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center text-white shadow-xl shadow-blue-500/20">
                    <User size={32}/>
                </div>
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white">{user?.login}</h1>
                    <p className="text-slate-500 dark:text-slate-400">Управление безопасностью и сессиями</p>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div className="md:col-span-1 space-y-6">
                    <div
                        className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm">
                        <div className="flex items-center gap-2 mb-6 text-slate-900 dark:text-white font-bold">
                            <Key size={20} className="text-blue-600"/>
                            <span>Смена пароля</span>
                        </div>

                        <form onSubmit={handleChangePassword} className="space-y-4">
                            <input
                                type="password" placeholder="Текущий пароль"
                                className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none dark:text-white"
                                value={passData.old} onChange={e => setPassPassData({...passData, old: e.target.value})}
                            />
                            <input
                                type="password" placeholder="Новый пароль"
                                className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none dark:text-white"
                                value={passData.new} onChange={e => setPassPassData({...passData, new: e.target.value})}
                            />
                            <input
                                type="password" placeholder="Повторите пароль"
                                className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none dark:text-white"
                                value={passData.confirm}
                                onChange={e => setPassPassData({...passData, confirm: e.target.value})}
                            />

                            {status.msg && (
                                <div
                                    className={`text-xs p-3 rounded-lg flex items-center gap-2 ${status.type === 'success' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                                    {status.type === 'success' ? <CheckCircle2 size={14}/> : <AlertCircle size={14}/>}
                                    {status.msg}
                                </div>
                            )}

                            <button
                                disabled={isChangingPass}
                                className="w-full bg-slate-900 dark:bg-white dark:text-slate-900 text-white py-3 rounded-xl font-bold hover:opacity-90 transition-all flex justify-center"
                            >
                                {isChangingPass ? <Loader2 className="animate-spin" size={20}/> : 'Обновить пароль'}
                            </button>
                        </form>
                    </div>
                </div>

                {/* Правая колонка: Сессии */}
                <div className="md:col-span-2 space-y-6">
                    <div
                        className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm">
                        <div className="flex justify-between items-center mb-6">
                            <div className="flex items-center gap-2 text-slate-900 dark:text-white font-bold">
                                <Shield size={20} className="text-blue-600"/>
                                <span>Активные сессии</span>
                            </div>
                            <button
                                onClick={handleLogoutAllManual}
                                className="text-xs font-bold text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 px-3 py-1.5 rounded-lg transition-colors"
                            >
                                Сбросить все
                            </button>
                        </div>

                        <div className="space-y-4">
                            {sessions.map((s) => {
                                const {location, device} = formatSessionInfo(s.user_agent);
                                const isOnline = new Date().getTime() - new Date(s.last_seen).getTime() < 300000;
                                return (
                                    <div key={s.id} className={`p-5 rounded-2xl border transition-all ${
                                        s.is_current ? 'border-blue-500 bg-blue-50/30' : 'border-slate-100 dark:border-slate-800'
                                    }`}>
                                        <div className="flex justify-between items-start">
                                            <div className="flex gap-4">
                                                <div className="relative">
                                                    <div
                                                        className={`p-3 rounded-xl ${s.is_current ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-400'}`}>
                                                        <Monitor size={24}/>
                                                    </div>
                                                    {isOnline && (
                                                        <div
                                                            className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 border-2 border-white dark:border-slate-900 rounded-full"></div>
                                                    )}
                                                </div>
                                                <div>
                                                    <p className="font-bold dark:text-white">{location}</p>
                                                    <p className="text-sm text-slate-500">{device}</p>

                                                    <div
                                                        className="flex items-center gap-1.5 mt-2 text-[11px] font-medium">
                                                        <Clock size={12} className="text-slate-400"/>
                                                        <span
                                                            className={isOnline ? "text-green-600" : "text-slate-400"}>
                                                            {isOnline ? 'В сети' : `Активность: ${formatLastSeen(s.last_seen)}`}
                                                         </span>
                                                    </div>
                                                </div>
                                            </div>

                                            {s.is_current && (
                                                <span
                                                    className="text-[10px] font-bold bg-blue-100 text-blue-700 px-2 py-1 rounded-lg uppercase">
                        Текущая
                    </span>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </div>
            </div>

            <div
                className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-100 dark:border-slate-800 shadow-sm mt-8">
                <h2 className="text-xl font-bold mb-6 dark:text-white flex items-center gap-2">
                    <Globe size={22} className="text-blue-600"/> Интеграции
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Legacy version Codeforces */}

                    <div
                        className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                        <div className="flex justify-between items-center mb-4">
                            <span className="font-bold dark:text-white">Codeforces</span>
                            {user?.is_codeforces_linked ? (
                                <span
                                    className="text-[10px] bg-green-100 text-green-700 px-2 py-1 rounded-full uppercase">Связан</span>
                            ) : (
                                <span
                                    className="text-[10px] bg-slate-200 text-slate-500 px-2 py-1 rounded-full uppercase">Не привязан</span>
                            )}
                        </div>
                        {user?.is_codeforces_linked ? (
                            <button onClick={handleCFUnlink}
                                    className="text-xs text-red-500 flex items-center gap-1 hover:underline">
                                <Unlink size={14}/> Отвязать
                            </button>
                        ) : (
                            <button onClick={() => setShowCfModal(true)}
                                    className="w-full bg-blue-600 text-white py-2 rounded-xl text-sm font-bold hover:bg-blue-700 transition-colors">
                                Привязать ключи API
                            </button>
                        )}
                    </div>

                    {/*<div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">*/}
                    {/*    <div className="flex justify-between items-center mb-4">*/}
                    {/*        <span className="font-bold dark:text-white">Codeforces</span>*/}
                    {/*        {user?.is_codeforces_linked ? (*/}
                    {/*            <div className="flex flex-col items-end">*/}
                    {/*                <span className="text-[10px] bg-green-100 text-green-700 px-2 py-1 rounded-full uppercase">Связан</span>*/}
                    {/*                <span className="text-xs font-bold text-blue-600 mt-1">@{user.is_codeforces_linked}</span>*/}
                    {/*            </div>*/}
                    {/*        ) : (*/}
                    {/*            <span className="text-[10px] bg-slate-200 text-slate-500 px-2 py-1 rounded-full uppercase">Не привязан</span>*/}
                    {/*        )}*/}
                    {/*    </div>*/}
                    {/*    {user?.is_codeforces_linked ? (*/}
                    {/*        <button onClick={handleCFUnlink} className="text-xs text-red-500 flex items-center gap-1 hover:underline">*/}
                    {/*            <Unlink size={14}/> Отвязать*/}
                    {/*        </button>*/}
                    {/*    ) : (*/}
                    {/*        <button onClick={handleCFStart} className="w-full bg-blue-600 text-white py-2 rounded-xl text-sm font-bold">*/}
                    {/*            Войти через Codeforces*/}
                    {/*        </button>*/}
                    {/*    )}*/}
                    {/*</div>*/}

                    <div
                        className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                        <div className="flex justify-between items-center mb-4">
                            <span className="font-bold dark:text-white italic">Yandex <span
                                className="text-red-500">Contest</span></span>
                            {user?.is_yandex_linked ? (
                                <span
                                    className="text-[10px] bg-green-100 text-green-700 px-2 py-1 rounded-full uppercase">Связан</span>
                            ) : (
                                <span
                                    className="text-[10px] bg-slate-200 text-slate-500 px-2 py-1 rounded-full uppercase">Не привязан</span>
                            )}
                        </div>
                        {user?.is_yandex_linked ? (
                            <button onClick={handleYandexUnlink}
                                    className="text-xs text-red-500 flex items-center gap-1 hover:underline">
                                <Unlink size={14}/> Отвязать
                            </button>
                        ) : (
                            <button onClick={handleYandexStart}
                                    className="w-full bg-red-600 text-white py-2 rounded-xl text-sm font-bold">
                                Войти через Яндекс
                            </button>
                        )}
                    </div>

                    <div
                        className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                        <div className="flex justify-between items-center mb-4">
                            <span className="font-bold dark:text-white text-orange-600">Polygon</span>
                            {user?.is_polygon_linked ? (
                                <span
                                    className="text-[10px] bg-green-100 text-green-700 px-2 py-1 rounded-full uppercase">Связан</span>
                            ) : (
                                <span
                                    className="text-[10px] bg-slate-200 text-slate-500 px-2 py-1 rounded-full uppercase">Не привязан</span>
                            )}
                        </div>
                        {user?.is_polygon_linked ? (
                            <button onClick={handlePolyUnlink}
                                    className="text-xs text-red-500 flex items-center gap-1 hover:underline">
                                <Unlink size={14}/> Отвязать
                            </button>
                        ) : (
                            <button onClick={() => setShowPolyModal(true)}
                                    className="w-full bg-orange-600 text-white py-2 rounded-xl text-sm font-bold hover:bg-orange-700 transition-colors">
                                Привязать Polygon API
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {showCfModal && (
                <div
                    className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
                    <div
                        className="bg-white dark:bg-slate-900 p-8 rounded-3xl w-full max-w-sm shadow-2xl animate-in zoom-in-95 duration-200">
                        <h3 className="text-xl font-bold mb-2 dark:text-white">API Ключи Codeforces</h3>
                        <p className="text-sm text-slate-500 mb-6">Создайте ключи в настройках профиля Codeforces
                            (вкладка API)</p>

                        <div className="space-y-4">
                            <div>
                                <label className="text-xs font-bold text-slate-400 ml-1">API KEY</label>
                                <input
                                    type="text"
                                    className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 mt-1 outline-none focus:ring-2 focus:ring-blue-500 dark:text-white"
                                    value={cfData.key}
                                    onChange={e => setCfData({...cfData, key: e.target.value})}
                                />
                            </div>
                            <div>
                                <label className="text-xs font-bold text-slate-400 ml-1">API SECRET</label>
                                <input
                                    type="password"
                                    className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 mt-1 outline-none focus:ring-2 focus:ring-blue-500 dark:text-white"
                                    value={cfData.secret}
                                    onChange={e => setCfData({...cfData, secret: e.target.value})}
                                />
                            </div>

                            <button
                                onClick={handleCFLink}
                                disabled={isLinkingCf || !cfData.key || !cfData.secret}
                                className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 disabled:opacity-50 transition-all flex justify-center"
                            >
                                {isLinkingCf ? <Loader2 className="animate-spin" size={20}/> : 'Сохранить ключи'}
                            </button>

                            <button
                                onClick={() => setShowCfModal(false)}
                                className="w-full text-slate-500 text-sm font-medium hover:text-slate-700 dark:hover:text-slate-300"
                            >
                                Отмена
                            </button>
                        </div>
                    </div>
                </div>
            )}
            {showPolyModal && (
                <div
                    className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
                    <div
                        className="bg-white dark:bg-slate-900 p-8 rounded-3xl w-full max-w-sm shadow-2xl animate-in zoom-in-95 duration-200">
                        <h3 className="text-xl font-bold mb-2 dark:text-white text-orange-600">Polygon API Ключи</h3>
                        <p className="text-sm text-slate-500 mb-6">Создайте ключи в настройках профиля Polygon</p>

                        <div className="space-y-4">
                            <div>
                                <label className="text-xs font-bold text-slate-400 ml-1">API KEY</label>
                                <input
                                    type="text"
                                    className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 mt-1 outline-none focus:ring-2 focus:ring-orange-500 dark:text-white"
                                    value={polyData.key}
                                    onChange={e => setPolyData({...polyData, key: e.target.value})}
                                />
                            </div>
                            <div>
                                <label className="text-xs font-bold text-slate-400 ml-1">API SECRET</label>
                                <input
                                    type="password"
                                    className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl p-3 mt-1 outline-none focus:ring-2 focus:ring-orange-500 dark:text-white"
                                    value={polyData.secret}
                                    onChange={e => setPolyData({...polyData, secret: e.target.value})}
                                />
                            </div>

                            <button
                                onClick={handlePolyLink}
                                disabled={isLinkingPoly || !polyData.key || !polyData.secret}
                                className="w-full bg-orange-600 text-white py-3 rounded-xl font-bold hover:bg-orange-700 disabled:opacity-50 transition-all flex justify-center"
                            >
                                {isLinkingPoly ? <Loader2 className="animate-spin" size={20}/> : 'Сохранить ключи'}
                            </button>

                            <button
                                onClick={() => setShowPolyModal(false)}
                                className="w-full text-slate-500 text-sm font-medium hover:text-slate-700 dark:hover:text-slate-300"
                            >
                                Отмена
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};