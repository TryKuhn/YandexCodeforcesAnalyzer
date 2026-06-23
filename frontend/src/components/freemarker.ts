// Minimal FreeMarker highlighter for the Polygon test-generation script.
//
// CodeMirror has no FreeMarker mode, so we define a tiny StreamLanguage that
// colours the parts that matter in our scripts: directives (<#assign>, <#list>,
// </#list>, <@...>), interpolations (${...}), comments (<#-- -->), numbers and
// strings. Everything else (the generator command lines) stays plain text.

import { StreamLanguage } from '@codemirror/language';
import type { Extension } from '@codemirror/state';

const freemarkerMode = StreamLanguage.define<{ inComment: boolean }>({
    startState: () => ({ inComment: false }),
    token(stream, state) {
        // Inside a <#-- ... --> comment block.
        if (state.inComment) {
            if (stream.match(/.*?-->/)) {
                state.inComment = false;
            } else {
                stream.skipToEnd();
            }
            return 'comment';
        }
        // Comment start.
        if (stream.match('<#--')) {
            if (!stream.match(/.*?-->/)) {
                state.inComment = true;
                stream.skipToEnd();
            }
            return 'comment';
        }
        // Directive tag: <#assign, </#list, <@macro, and their closing '>'.
        if (stream.match(/<\/?[#@][\w.]*/)) return 'keyword';
        // Interpolation ${ ... }.
        if (stream.match(/\$\{[^}]*\}?/)) return 'string';
        // Quoted strings.
        if (stream.match(/"(?:[^"\\]|\\.)*"/)) return 'string';
        if (stream.match(/'(?:[^'\\]|\\.)*'/)) return 'string';
        // Numbers.
        if (stream.match(/\b\d+\b/)) return 'number';
        // Stray angle bracket (directive close, shell redirect '>').
        if (stream.match(/[<>]/)) return 'operator';
        stream.next();
        return null;
    },
});

export const freemarkerLanguage: Extension = freemarkerMode;
