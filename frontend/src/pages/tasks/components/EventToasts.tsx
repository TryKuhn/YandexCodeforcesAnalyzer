// pages/tasks/components/EventToasts.tsx
//
// Notifications about what changed in the problem (on Polygon behind our back,
// or a finished package build). Each toast hides itself after a while.

import { useEffect } from 'react';
import { Bell, Package, RefreshCw, X } from 'lucide-react';
import type { AiEvent } from '../../../api/ai';

const HIDE_AFTER_MS = 12000;
const HIDE_CHANGE_AFTER_MS = 60000; // a change on Polygon offers to reload the tab: keep it longer
const MAX_CHANGES = 6;

interface Props {
    events: AiEvent[];
    onDismiss: (id: number) => void;
    /** Re-read the open tab (unsaved edits in it are lost). */
    onReload?: (id: number) => void;
}

export const EventToasts = ({ events, onDismiss, onReload }: Props) => (
    <div className="fixed bottom-4 left-4 z-50 flex flex-col gap-2 max-w-sm w-[calc(100%-2rem)] sm:w-96 pointer-events-none">
        {events.map(e => <Toast key={e.id} event={e} onDismiss={onDismiss} onReload={onReload} />)}
    </div>
);

const Toast = ({ event, onDismiss, onReload }: {
    event: AiEvent; onDismiss: (id: number) => void; onReload?: (id: number) => void;
}) => {
    useEffect(() => {
        const ms = event.source === 'build' ? HIDE_AFTER_MS : HIDE_CHANGE_AFTER_MS;
        const timer = setTimeout(() => onDismiss(event.id), ms);
        return () => clearTimeout(timer);
    }, [event.id, event.source, onDismiss]);

    const build = event.source === 'build';
    const failed = build && event.changes.some(c => c.state && c.state !== 'READY');
    const header = build ? (failed ? 'Сборка пакета' : 'Пакет собран') : 'Задача изменилась в Polygon';

    return (
        <div className={`pointer-events-auto rounded-2xl border shadow-lg px-3 py-2.5 text-xs bg-white dark:bg-slate-900
            ${failed ? 'border-red-200 dark:border-red-800' : 'border-slate-200 dark:border-slate-700'}`}>
            <div className="flex items-center gap-2 mb-1">
                {build
                    ? <Package size={13} className={failed ? 'text-red-500' : 'text-green-500'} />
                    : <Bell size={13} className="text-blue-500" />}
                <span className="font-bold text-slate-700 dark:text-slate-200 flex-1">{header}</span>
                <button onClick={() => onDismiss(event.id)} className="text-slate-400 hover:text-slate-600">
                    <X size={12} />
                </button>
            </div>
            {event.changes.length > 0 ? (
                <ul className="space-y-0.5 text-[11px] text-slate-600 dark:text-slate-300">
                    {event.changes.slice(0, MAX_CHANGES).map((c, i) => (
                        <li key={i} className="break-words">• {c.text}</li>
                    ))}
                    {event.changes.length > MAX_CHANGES && (
                        <li className="text-slate-400">и ещё {event.changes.length - MAX_CHANGES}</li>
                    )}
                </ul>
            ) : (
                <p className="text-[11px] text-slate-600 dark:text-slate-300">{event.title}</p>
            )}
            {!build && onReload && (
                <button
                    onClick={() => onReload(event.id)}
                    className="mt-1.5 flex items-center gap-1 text-[11px] font-bold text-blue-600 dark:text-blue-400 hover:underline"
                >
                    <RefreshCw size={11} /> Обновить вкладку
                </button>
            )}
        </div>
    );
};
