// pages/tasks/useAiSession.ts
//
// State of the AI workspace of one problem: chat messages, notifications about
// changes on Polygon, the active background run and the latest package build.
// The page polls the service: often while a run is active, rarely otherwise;
// the problem is re-read from Polygon on open and every SYNC_INTERVAL_MS.

import { useCallback, useEffect, useRef, useState } from 'react';
import {
    aiApi, errorText, isActive,
    type AiBuild, type AiEvent, type AiMessage, type AiRun, type AiSession, type ChatContext,
} from '../../api/ai';

const ACTIVE_POLL_MS = 2000;
const IDLE_POLL_MS = 15000;
const SYNC_INTERVAL_MS = 5 * 60 * 1000;

interface Options {
    onEvents?: (events: AiEvent[]) => void;
    onRunFinished?: (run: AiRun) => void;
}

const mergeMessages = (prev: AiMessage[], next: AiMessage[]) => {
    if (!next.length) return prev;
    const known = new Set(prev.map(m => m.id));
    return [...prev, ...next.filter(m => !known.has(m.id))];
};

export const useAiSession = (polygonId: number, { onEvents, onRunFinished }: Options = {}) => {
    const [session, setSession] = useState<AiSession | null>(null);
    const [messages, setMessages] = useState<AiMessage[]>([]);
    const [activeRun, setActiveRun] = useState<AiRun | null>(null);
    const [latestBuild, setLatestBuild] = useState<AiBuild | null>(null);
    const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
    const [syncError, setSyncError] = useState<string | null>(null);
    const [syncing, setSyncing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const lastMessageId = useRef(0);
    const lastEventId = useRef(0);
    const runRef = useRef<AiRun | null>(null);
    // bumped by every poll and local change: an answer to an older poll is dropped
    // (it could otherwise "finish" a run that was started after it was sent)
    const generation = useRef(0);
    const callbacks = useRef<Options>({ onEvents, onRunFinished });
    useEffect(() => { callbacks.current = { onEvents, onRunFinished }; });

    const sessionId = session?.session_id ?? null;

    const applyRun = useCallback((run: AiRun | null) => {
        const previous = runRef.current;
        runRef.current = run;
        setActiveRun(run);
        if (previous && isActive(previous) && (!run || run.id !== previous.id)) {
            callbacks.current.onRunFinished?.(previous);
        }
    }, []);

    const handleEvents = useCallback((sid: string, events: AiEvent[]) => {
        events = events.filter(e => e.id > lastEventId.current);
        if (!events.length) return;
        lastEventId.current = Math.max(lastEventId.current, ...events.map(e => e.id));
        callbacks.current.onEvents?.(events);
        aiApi.seen(sid, lastEventId.current).catch(() => { /* not critical */ });
    }, []);

    const poll = useCallback(async () => {
        if (!sessionId) return;
        const mine = ++generation.current;
        try {
            const state = await aiApi.state(sessionId, lastMessageId.current, lastEventId.current);
            if (mine !== generation.current) return;
            if (state.messages.length) {
                lastMessageId.current = Math.max(lastMessageId.current, ...state.messages.map(m => m.id));
                setMessages(prev => mergeMessages(prev, state.messages));
            }
            handleEvents(sessionId, state.events);
            applyRun(state.active_run);
            setLatestBuild(state.latest_build);
            setLastSyncedAt(state.last_synced_at);
            setSyncError(state.sync_error);
        } catch { /* transient: next poll */ }
    }, [sessionId, applyRun, handleEvents]);

    const sync = useCallback(async () => {
        if (!sessionId) return;
        setSyncing(true);
        try {
            const result = await aiApi.sync(sessionId);
            if (result.last_synced_at) setLastSyncedAt(result.last_synced_at);
            setSyncError(result.sync_error ?? null);
        } catch (e) {
            setSyncError(errorText(e, 'Не удалось синхронизироваться с Polygon'));
        } finally {
            setSyncing(false);
        }
        await poll();
    }, [sessionId, poll]);

    // open the session (and pull the problem from Polygon)
    useEffect(() => {
        if (!polygonId) return;
        let cancelled = false;
        generation.current++;
        setError(null);
        setSession(null);
        setMessages([]);
        runRef.current = null;
        setActiveRun(null);
        aiApi.open(polygonId)
            .then(opened => {
                if (cancelled) return;
                const { messages: history, unseen_events, last_event_id, active_run, latest_build, ...rest } = opened;
                setSession(rest);
                setMessages(history);
                lastMessageId.current = history.length ? history[history.length - 1].id : 0;
                lastEventId.current = last_event_id;
                runRef.current = active_run;
                setActiveRun(active_run);
                setLatestBuild(latest_build);
                setLastSyncedAt(rest.last_synced_at);
                setSyncError(rest.sync_error);
                if (unseen_events.length) {
                    callbacks.current.onEvents?.(unseen_events);
                    aiApi.seen(rest.session_id, last_event_id).catch(() => {});
                }
            })
            .catch(e => !cancelled && setError(errorText(e, 'Сервис ИИ недоступен')));
        return () => { cancelled = true; };
    }, [polygonId]);

    // first sync right after opening
    useEffect(() => {
        if (sessionId) sync();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

    // polling: fast while something runs
    const running = isActive(activeRun);
    useEffect(() => {
        if (!sessionId) return;
        const timer = setInterval(poll, running ? ACTIVE_POLL_MS : IDLE_POLL_MS);
        return () => clearInterval(timer);
    }, [sessionId, running, poll]);

    // periodic re-read of the problem while the page is open
    useEffect(() => {
        if (!sessionId) return;
        const timer = setInterval(() => { if (!document.hidden) sync(); }, SYNC_INTERVAL_MS);
        return () => clearInterval(timer);
    }, [sessionId, sync]);

    const send = useCallback(async (text: string, context?: ChatContext) => {
        if (!sessionId) return;
        const { message, run } = await aiApi.send(sessionId, text, context);
        generation.current++;
        lastMessageId.current = Math.max(lastMessageId.current, message.id);
        setMessages(prev => mergeMessages(prev, [message]));
        applyRun(run);
    }, [sessionId, applyRun]);

    /** A run started elsewhere (build button, groups editor, generation form). */
    const track = useCallback((run: AiRun) => {
        generation.current++;
        applyRun(run);
        setTimeout(poll, 300);
    }, [applyRun, poll]);

    const cancel = useCallback(async () => {
        if (!runRef.current) return;
        try {
            const run = await aiApi.cancel(runRef.current.id);
            generation.current++;
            applyRun(run);
        } catch { /* ignore */ }
        poll();
    }, [applyRun, poll]);

    const update = useCallback(async (body: { model?: string; problem_type?: string; auto_build?: boolean }) => {
        if (!sessionId) return;
        setSession(await aiApi.patch(sessionId, body));
    }, [sessionId]);

    return {
        session, sessionId, messages, activeRun, latestBuild, lastSyncedAt, syncError, syncing, error,
        send, sync, poll, track, cancel, update,
    };
};

export type AiSessionState = ReturnType<typeof useAiSession>;
