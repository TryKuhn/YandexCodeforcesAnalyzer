import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/instance';
import {useAuthStore} from "../store/useAuthStore.ts";

export const YandexCallback = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const processed = useRef(false);

    useEffect(() => {
        if (processed.current) return;
        processed.current = true;

        const code = searchParams.get('code');
        if (!code) {
            navigate('/profile');
            return;
        }

        api.post('/yandex/callback', { code })
            .then(async () => {
                await useAuthStore.getState().fetchUser();
                navigate('/profile');
            })
            .catch((e) => {
                console.error(e);
                alert('Ошибка привязки: ' + (e.response?.data?.detail || e.message));
                navigate('/profile');
            });
    }, []);

    return (
        <div className="flex items-center justify-center min-h-screen">
            <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <p className="text-slate-500">Привязываем Яндекс аккаунт...</p>
            </div>
        </div>
    );
};