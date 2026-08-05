/** Which portal this build is: fixed at build time by vite's `define`. */
export type Portal = 'participant' | 'jury';

declare const __PORTAL__: Portal;

export const PORTAL: Portal = __PORTAL__;

// literals, so the bundler can drop the other portal's route tree entirely
export const isJuryPortal = PORTAL === 'jury';
export const isParticipantPortal = PORTAL === 'participant';

/** Only these roles may open the jury portal at all. */
export const JURY_ROLES = ['Admin'];

export function mayEnterJury(role: string | null | undefined): boolean {
    return !!role && JURY_ROLES.includes(role);
}
