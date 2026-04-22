import { create } from 'zustand';
import {persist} from "zustand/middleware";
import {api} from "../api/instance.ts";

interface User {
    id: string;
    login: string;
    email: string;
    role_id: string;
    is_yandex_linked: boolean;
    is_codeforces_linked: boolean;
    is_polygon_linked: boolean;
}

interface AuthState {
    user: User | null;
    accessToken: string | null;
    refreshToken: string | null;
    tokenType: string | null;
    isAuthenticated: boolean;
    setAuthenticated: (accessToken: string, refreshToken: string, tokenType: string) => void;
    setUser: (user: User) => void;
    updateTokens: (accessToken: string, refreshToken: string, tokenType: string) => void;
    fetchUser: () => Promise<void>;
    logout: () => void;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set) => ({
            user: null,
            accessToken: null,
            refreshToken: null,
            tokenType: null,
            isAuthenticated: false,
            setAuthenticated: (accessToken, refreshToken, tokenType) => {
                set({accessToken, refreshToken, tokenType, isAuthenticated: true});
            },
            setUser: (user) => set({user}),
            updateTokens: (accessToken, refreshToken, tokenType) => {
                set({accessToken, refreshToken, tokenType});
            },
            fetchUser: async () => {
                try {
                    const res = await api.get('/auth/me');
                    set({ user: res.data });
                } catch (e) {
                    console.error("Failed to fetch user", e);
                }
            },
            logout: () => {
                set({user: null, accessToken: null, refreshToken: null, tokenType: null, isAuthenticated: false});
            },
        }),
        {
            name: 'auth-storage'
        }
    )
);
