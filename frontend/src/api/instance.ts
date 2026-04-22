import axios from 'axios';
import {useAuthStore} from "../store/useAuthStore.ts";

const API_URL = import.meta.env.VITE_API_URL;

export const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
})

api.interceptors.request.use((config) => {
    const {accessToken, tokenType} = useAuthStore.getState();
    if (accessToken && config.headers) {
        config.headers.Authorization = `${tokenType} ${accessToken}`;
    }
    return config;
});

let isRefreshing = false;
let refreshSubscribers: any[] = [];

const subscribeTokenRefresh = (cb: any) => {
    refreshSubscribers.push(cb);
}

const onRefreshed = (token: any, type: any) => {
    refreshSubscribers.map((cb) => cb(token, type));
    refreshSubscribers = [];
}

api.interceptors.response.use((response) => response, async (error) => {
    const {config, response} = error;
    const request = config;

    if (response?.status === 401 && !request._retry) {
        if (isRefreshing) {
            return new Promise(resolve => {
                subscribeTokenRefresh((newToken: any, newType: any) => {
                    request.headers.Authorization = `${newType} ${newToken}`;
                    resolve(api(request));
                })
            });
        }

        request._retry = true;
        isRefreshing = true;

        const {accessToken, refreshToken, tokenType} = useAuthStore.getState();

        if (refreshToken) {
            try {
                const response = await axios.post(`${import.meta.env.VITE_API_URL}/auth/refresh`, {
                    access_token: accessToken,
                    refresh_token: refreshToken,
                    token_type: tokenType,
                })

                const {access_token, refresh_token, token_type} = response.data;

                useAuthStore.getState().updateTokens(access_token, refresh_token, token_type);

                isRefreshing = false;
                onRefreshed(access_token, token_type);

                request.headers.Authorization = `${token_type} ${access_token}`;
                return api(request);
            } catch (refreshError) {
                isRefreshing = false;
                refreshSubscribers = [];

                useAuthStore.getState().logout();

                if (window.location.pathname !== '/login') {
                    window.location.href = '/login';
                }

                return Promise.reject(refreshError);
            }
        }
    }

    return Promise.reject(error);
});
