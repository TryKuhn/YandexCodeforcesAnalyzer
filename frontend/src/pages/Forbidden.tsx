import {useAuthStore} from '../store/useAuthStore';

/** Shown when a non-jury account opens the jury portal. */
export function Forbidden() {
    const {user, logout} = useAuthStore();

    return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
            <div className="text-6xl font-bold text-gray-400">403</div>
            <h1 className="text-2xl font-semibold">Доступ только для жюри</h1>
            <p className="max-w-md text-gray-500">
                Аккаунт <span className="font-mono">{user?.login}</span> имеет роль{' '}
                <span className="font-mono">{user?.role ?? 'без роли'}</span>. Портал жюри
                доступен только преподавателям и администраторам.
            </p>
            <p className="text-gray-500">
                Участникам — портал соревнований на отдельном адресе.
            </p>
            <button
                onClick={logout}
                className="rounded-lg border px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-800"
            >
                Выйти
            </button>
        </div>
    );
}
