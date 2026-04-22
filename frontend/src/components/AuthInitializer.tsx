import { useEffect } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { api } from '../api/instance';

export const AuthInitializer = () => {
    const { isAuthenticated, user, setUser, logout } = useAuthStore();

    useEffect(() => {
        const fetchMe = async () => {
            if (isAuthenticated && !user) {
                try {
                    const res = await api.get('/auth/me');
                    setUser(res.data);
                } catch (e) {
                    console.error("Session expired or invalid");
                    logout();
                }
            }
        };
        fetchMe();
    }, [isAuthenticated, user]);

    return null;
};
