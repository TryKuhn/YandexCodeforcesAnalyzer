// components/CodeEditor.tsx

import CodeMirror from '@uiw/react-codemirror';
import type { Extension } from '@codemirror/state';
import { langs } from '@uiw/codemirror-extensions-langs';
import { useThemeStore } from '../store/useThemeStore';
import { freemarkerLanguage } from './freemarker';

// Map file extension -> CodeMirror language
const EXT_LANG: Record<string, keyof typeof langs> = {
    cpp: 'cpp', cc: 'cpp', cxx: 'cpp', h: 'cpp', hpp: 'cpp', c: 'c',
    py: 'python', java: 'java', kt: 'kt', go: 'go', rs: 'rs',
    cs: 'cs', pas: 'pas', js: 'js', ts: 'ts',
    sh: 'sh', json: 'json', xml: 'xml', html: 'html', css: 'css',
    md: 'markdown', sql: 'sql', tex: 'tex', rb: 'rb', php: 'php',
};

export function detectLanguage(fileName: string): Extension | null {
    const ext = fileName.split('.').pop()?.toLowerCase() ?? '';
    // FreeMarker test-generation script (no built-in CodeMirror mode).
    if (ext === 'ftl' || ext === 'freemarker') return freemarkerLanguage;
    const langKey = EXT_LANG[ext];
    if (!langKey || typeof langs[langKey] !== 'function') return null;
    try {
        return langs[langKey]();
    } catch {
        return null;
    }
}

interface Props {
    value: string;
    onChange?: (value: string) => void;
    fileName?: string;
    readOnly?: boolean;
    minHeight?: string;
    maxHeight?: string;
    height?: string;
    placeholder?: string;
    className?: string;
}

export const CodeEditor = ({
    value, onChange, fileName = '', readOnly = false,
    minHeight, maxHeight, height, placeholder, className = '',
}: Props) => {
    const { theme } = useThemeStore();
    const isDark =
        theme === 'dark' ||
        (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

    const lang = detectLanguage(fileName);

    return (
        <div className={`border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden text-[13px] ${className}`}>
            <CodeMirror
                value={value}
                onChange={onChange}
                readOnly={readOnly}
                theme={isDark ? 'dark' : 'light'}
                extensions={lang ? [lang] : []}
                minHeight={minHeight}
                maxHeight={maxHeight}
                height={height}
                placeholder={placeholder}
                basicSetup={{
                    lineNumbers: true,
                    foldGutter: true,
                    highlightActiveLine: !readOnly,
                    highlightActiveLineGutter: !readOnly,
                    indentOnInput: true,
                    bracketMatching: true,
                    closeBrackets: true,
                    autocompletion: false,
                }}
            />
        </div>
    );
};
