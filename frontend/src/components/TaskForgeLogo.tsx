export const TaskForgeIcon = ({ size = 32, className = '' }: { size?: number; className?: string }) => (
    <svg
        viewBox="80 40 240 240"
        width={size}
        height={size}
        xmlns="http://www.w3.org/2000/svg"
        className={className}
    >
        <defs>
            <linearGradient id="tfi-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#f59e0b"/>
                <stop offset="50%" stopColor="#f97316"/>
                <stop offset="100%" stopColor="#ef4444"/>
            </linearGradient>
            <linearGradient id="tfi-soft" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.12"/>
                <stop offset="100%" stopColor="#ef4444" stopOpacity="0.12"/>
            </linearGradient>
        </defs>
        <g transform="translate(80, 40)">
            <rect x="0" y="0" width="240" height="240" rx="56" fill="url(#tfi-soft)"/>
            <rect x="0" y="0" width="240" height="240" rx="56" fill="none" stroke="url(#tfi-grad)" strokeWidth="2" opacity="0.4"/>
            <path d="M 120 20 L 206.6 70 L 206.6 170 L 120 220 L 33.4 170 L 33.4 70 Z"
                  fill="none" stroke="url(#tfi-grad)" strokeWidth="7" strokeLinejoin="round" opacity="0.85"/>
            <path d="M 120 65 L 170 125 L 145 125 L 145 195 L 95 195 L 95 125 L 70 125 Z"
                  fill="url(#tfi-grad)"/>
            <path d="M 185 81 L 188.9 91.1 L 199 95 L 188.9 98.9 L 185 109 L 181.1 98.9 L 171 95 L 181.1 91.1 Z"
                  fill="url(#tfi-grad)" opacity="0.9"/>
            <circle cx="185" cy="95" r="4" fill="white" opacity="0.9"/>
        </g>
    </svg>
);
