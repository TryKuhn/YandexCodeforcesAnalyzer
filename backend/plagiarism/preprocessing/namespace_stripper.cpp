#include "namespace_stripper.h"

static bool IsIdentChar(char c) {
    return (c >= 'a' && c <= 'z') ||
           (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') ||
           c == '_';
}

std::string StripNamespaceQualifiers(const std::string& code) {
    std::string result;
    result.reserve(code.size());

    const std::size_t n = code.size();
    std::size_t i = 0;
    bool in_string = false;
    bool in_char_lit = false;
    bool escape_next = false;

    while (i < n) {
        char c = code[i];

        if (in_string) {
            result += c;
            if (escape_next)      { escape_next = false; }
            else if (c == '\\')   { escape_next = true; }
            else if (c == '"')    { in_string = false; }
            ++i;
            continue;
        }

        if (in_char_lit) {
            result += c;
            if (escape_next)      { escape_next = false; }
            else if (c == '\\')   { escape_next = true; }
            else if (c == '\'')   { in_char_lit = false; }
            ++i;
            continue;
        }

        if (c == '"')  { in_string = true;  escape_next = false; result += c; ++i; continue; }
        if (c == '\'') { in_char_lit = true; escape_next = false; result += c; ++i; continue; }

        // Strip a leading :: (global-namespace qualifier like ::sort)
        if (c == ':' && i + 1 < n && code[i + 1] == ':' &&
                i + 2 < n && IsIdentChar(code[i + 2]) &&
                (i == 0 || !IsIdentChar(code[i - 1]))) {
            i += 2;
            continue;
        }

        // Start of an identifier — check whether it is a namespace prefix
        if (IsIdentChar(c) && (i == 0 || !IsIdentChar(code[i - 1]))) {
            const std::size_t ident_start = i;
            while (i < n && IsIdentChar(code[i])) ++i;

            // Identifier followed by ::IDENT — it is a namespace/scope prefix: discard it
            if (i + 1 < n && code[i] == ':' && code[i + 1] == ':' &&
                    i + 2 < n && IsIdentChar(code[i + 2])) {
                i += 2;  // skip ::, loop re-enters for the next component
            } else {
                result.append(code, ident_start, i - ident_start);
            }
            continue;
        }

        result += c;
        ++i;
    }

    return result;
}
