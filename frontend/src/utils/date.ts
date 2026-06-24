// Backend serialises timestamps as UTC but often without a timezone designator
// (e.g. "2026-06-24T09:53:00"). JS `new Date()` parses a designator-less ISO
// string as LOCAL time, which shifts every displayed time by the viewer's UTC
// offset. Treat such strings as UTC by appending 'Z'; leave already-zoned
// strings (…Z / …+03:00) untouched.
export function parseServerDate(s: string | null | undefined): Date {
    if (!s) return new Date(NaN);
    let str = s.trim().replace(' ', 'T');
    if (!/([zZ]|[+-]\d{2}:?\d{2})$/.test(str)) str += 'Z';
    return new Date(str);
}
