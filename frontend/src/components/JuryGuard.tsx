import type {ReactNode} from 'react';
import {useAuthStore} from '../store/useAuthStore';
import {isJuryPortal, mayEnterJury} from '../portal';
import {Forbidden} from '../pages/Forbidden';

/** Blocks the jury portal for anyone without a jury role. */
export function JuryGuard({children}: {children: ReactNode}) {
    const {user} = useAuthStore();

    // the participant build never renders jury routes, so nothing to guard there
    if (!isJuryPortal) return <>{children}</>;

    // the role arrives with /auth/me; until then show nothing rather than a flash of content
    if (!user) return null;

    return mayEnterJury(user.role) ? <>{children}</> : <Forbidden/>;
}
