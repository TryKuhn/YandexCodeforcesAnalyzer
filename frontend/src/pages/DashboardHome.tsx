import { Link } from 'react-router-dom';
import {
    Trophy, FileCode, ShieldCheck, Sparkles, Key, User,
    ArrowRight, Globe, Cpu, AlertCircle, CheckCircle2,
    ExternalLink, BarChart3, Users,
} from 'lucide-react';

const SectionTitle = ({ children }: { children: React.ReactNode }) => (
    <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-4">{children}</h2>
);

const FeatureCard = ({ icon: Icon, color, title, desc }: any) => (
    <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-100 dark:border-slate-800 flex gap-4 items-start">
        <div className={`p-2.5 rounded-xl shrink-0 ${color}`}>
            <Icon size={20} className="text-white" />
        </div>
        <div>
            <p className="font-bold text-sm dark:text-white mb-1">{title}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">{desc}</p>
        </div>
    </div>
);

const StepCard = ({ n, title, desc, action }: any) => (
    <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-3 mb-3">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-500 text-white text-xs font-black flex items-center justify-center shrink-0 shadow shadow-violet-500/30">
                {n}
            </div>
            <p className="font-bold text-sm dark:text-white">{title}</p>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed mb-3">{desc}</p>
        {action}
    </div>
);

const HintBox = ({ icon: Icon, color, title, children }: any) => (
    <div className={`p-4 rounded-2xl border ${color} flex gap-3`}>
        <Icon size={18} className="shrink-0 mt-0.5" />
        <div>
            <p className="font-bold text-sm mb-1">{title}</p>
            <div className="text-xs leading-relaxed space-y-1">{children}</div>
        </div>
    </div>
);

export const DashboardHome = () => {
    return (
        <div className="space-y-10 animate-in fade-in duration-500">
            <div className="bg-gradient-to-br from-violet-600 to-fuchsia-600 text-white rounded-3xl p-8 shadow-xl shadow-violet-500/20">
                <p className="text-xs font-black uppercase tracking-widest text-violet-200 mb-2">Добро пожаловать</p>
                <h1 className="text-3xl font-extrabold mb-3">TaskForge</h1>
                <p className="text-violet-100 text-sm leading-relaxed max-w-xl">
                    Инструмент для преподавателей и организаторов олимпиад: загружайте контесты с Codeforces и Yandex,
                    просматривайте таблицу результатов, проверяйте решения на плагиат и создавайте задачи с помощью ИИ.
                </p>
            </div>

            <div>
                <SectionTitle>Основные возможности</SectionTitle>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    <FeatureCard
                        icon={Globe}
                        color="bg-blue-500"
                        title="Импорт контестов"
                        desc="Загружайте контесты с Codeforces и Yandex Contest одним кликом — результаты, посылки и исходники синхронизируются автоматически."
                    />
                    <FeatureCard
                        icon={Trophy}
                        color="bg-amber-500"
                        title="Таблица результатов"
                        desc="Ранклист с поиском, пагинацией и поддержкой форматов ICPC и IOI. Забаненные за плагиат ячейки подсвечиваются отдельным цветом."
                    />
                    <FeatureCard
                        icon={FileCode}
                        color="bg-emerald-500"
                        title="Просмотр посылок"
                        desc="Полный список решений с фильтрами по задаче, языку и вердикту. Исходный код открывается в одном клике."
                    />
                    <FeatureCard
                        icon={ShieldCheck}
                        color="bg-red-500"
                        title="Антиплагиат"
                        desc="C++ движок на LSH-хэшировании сравнивает решения по задачам. Два порога: порог отображения (для ревью) и порог автобана (обнуляет баллы)."
                    />
                    <FeatureCard
                        icon={BarChart3}
                        color="bg-purple-500"
                        title="Аналитика"
                        desc="История всех отчётов антиплагиата с разбивкой по парам и задачам. Ручной бан прямо из режима сравнения кода."
                    />
                    <FeatureCard
                        icon={Sparkles}
                        color="bg-fuchsia-500"
                        title="AI Создание задач"
                        desc="Генерируйте условия, тесты и решения для задач с помощью Claude, Gemini или GPT. Готовые файлы экспортируются в Polygon."
                    />
                </div>
            </div>

            <div>
                <SectionTitle>Как начать работу</SectionTitle>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <StepCard
                        n={1}
                        title="Привяжите аккаунты"
                        desc="Для загрузки контестов с Codeforces или создания задач в Polygon нужно добавить API-ключи в профиле."
                        action={
                            <Link to="/profile" className="inline-flex items-center gap-1.5 text-xs font-bold text-violet-600 hover:text-violet-800 transition-colors">
                                <User size={13} /> Открыть профиль <ArrowRight size={12} />
                            </Link>
                        }
                    />
                    <StepCard
                        n={2}
                        title="Загрузите контест"
                        desc="Перейдите в «Соревнования», нажмите «Загрузить» и введите ID контеста. Данные загрузятся автоматически."
                        action={
                            <Link to="/contests" className="inline-flex items-center gap-1.5 text-xs font-bold text-violet-600 hover:text-violet-800 transition-colors">
                                <Trophy size={13} /> Соревнования <ArrowRight size={12} />
                            </Link>
                        }
                    />
                    <StepCard
                        n={3}
                        title="Проверьте результаты"
                        desc="В таблице контеста — ранклист, посылки и анализ плагиата. Настройте пороги и запустите проверку."
                        action={
                            <span className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-400">
                                <ShieldCheck size={13} /> Антиплагиат доступен внутри контеста
                            </span>
                        }
                    />
                    <StepCard
                        n={4}
                        title="Создавайте задачи с ИИ"
                        desc="В разделе AI Создание выберите модель, опишите задачу и получите готовые файлы для Polygon."
                        action={
                            <Link to="/ai-tasks" className="inline-flex items-center gap-1.5 text-xs font-bold text-violet-600 hover:text-violet-800 transition-colors">
                                <Sparkles size={13} /> AI Создание <ArrowRight size={12} />
                            </Link>
                        }
                    />
                </div>
            </div>

            <div>
                <SectionTitle>Где взять API-ключи</SectionTitle>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <HintBox
                        icon={Key}
                        color="bg-blue-50 dark:bg-blue-950/30 border-blue-100 dark:border-blue-900/40 text-blue-700 dark:text-blue-300"
                        title="Codeforces API Key + Secret"
                    >
                        <p className="text-blue-600 dark:text-blue-400">
                            Зайдите на codeforces.com → «Настройки» → вкладка <strong>«API»</strong>.
                            Нажмите «Добавить ключ», скопируйте <code className="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">Key</code> и{' '}
                            <code className="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">Secret</code>.
                        </p>
                        <p className="text-blue-500 dark:text-blue-500 mt-1">
                            Необходим для импорта контестов и загрузки исходников посылок.
                        </p>
                        <a
                            href="https://codeforces.com/settings/api"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 font-bold mt-2 hover:underline"
                        >
                            Открыть настройки <ExternalLink size={11} />
                        </a>
                    </HintBox>

                    <HintBox
                        icon={Cpu}
                        color="bg-emerald-50 dark:bg-emerald-950/30 border-emerald-100 dark:border-emerald-900/40 text-emerald-700 dark:text-emerald-300"
                        title="Polygon API Key + Secret"
                    >
                        <p className="text-emerald-600 dark:text-emerald-400">
                            Зайдите на polygon.codeforces.com → <strong>«Настройки»</strong> (иконка в правом верхнем углу).
                            Скопируйте <code className="bg-emerald-100 dark:bg-emerald-900/40 px-1 rounded">API Key</code> и{' '}
                            <code className="bg-emerald-100 dark:bg-emerald-900/40 px-1 rounded">API Secret</code>.
                        </p>
                        <p className="text-emerald-500 dark:text-emerald-500 mt-1">
                            Необходим для экспорта задач, созданных ИИ, в Polygon.
                        </p>
                        <a
                            href="https://polygon.codeforces.com"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 font-bold mt-2 hover:underline"
                        >
                            Открыть Polygon <ExternalLink size={11} />
                        </a>
                    </HintBox>

                    <HintBox
                        icon={Globe}
                        color="bg-amber-50 dark:bg-amber-950/30 border-amber-100 dark:border-amber-900/40 text-amber-700 dark:text-amber-300"
                        title="Yandex Contest"
                    >
                        <p className="text-amber-600 dark:text-amber-400">
                            Привязка Yandex Contest выполняется через OAuth — кнопка «Войти через Yandex» в профиле.
                            Отдельный API-ключ не нужен.
                        </p>
                        <p className="text-amber-500 dark:text-amber-500 mt-1">
                            Необходим для импорта контестов с Yandex Contest (контест должен быть доступен вашему аккаунту).
                        </p>
                    </HintBox>

                    <HintBox
                        icon={Users}
                        color="bg-purple-50 dark:bg-purple-950/30 border-purple-100 dark:border-purple-900/40 text-purple-700 dark:text-purple-300"
                        title="Участники контеста"
                    >
                        <p className="text-purple-600 dark:text-purple-400">
                            Имена участников загружаются автоматически при импорте контеста. Для Codeforces — через API.
                            Для Yandex — через OAuth.
                        </p>
                        <p className="text-purple-500 dark:text-purple-500 mt-1">
                            Если имена не подтянулись — убедитесь, что API-ключи активны, и повторно загрузите контест.
                        </p>
                    </HintBox>
                </div>
            </div>

            <div>
                <SectionTitle>Как работает антиплагиат</SectionTitle>
                <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-100 dark:border-slate-800 p-6 space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
                        <div className="flex gap-3 items-start">
                            <CheckCircle2 size={16} className="text-green-500 shrink-0 mt-0.5" />
                            <div>
                                <p className="font-bold dark:text-white mb-0.5">LSH + Trigram</p>
                                <p className="text-xs text-slate-500">Locality Sensitive Hashing по триграмам токенов — быстрая предфильтрация кандидатов без полного O(n²) сравнения.</p>
                            </div>
                        </div>
                        <div className="flex gap-3 items-start">
                            <CheckCircle2 size={16} className="text-green-500 shrink-0 mt-0.5" />
                            <div>
                                <p className="font-bold dark:text-white mb-0.5">AST-сравнение</p>
                                <p className="text-xs text-slate-500">Для подозрительных пар запускается синтаксический анализ (Clang AST). Переименование переменных и рефакторинг не спасут.</p>
                            </div>
                        </div>
                        <div className="flex gap-3 items-start">
                            <CheckCircle2 size={16} className="text-green-500 shrink-0 mt-0.5" />
                            <div>
                                <p className="font-bold dark:text-white mb-0.5">Два порога</p>
                                <p className="text-xs text-slate-500"><strong>Порог отображения</strong> — показывает пары для ревью. <strong>Порог автобана</strong> — обнуляет баллы автоматически. Оба настраиваются перед запуском.</p>
                            </div>
                        </div>
                    </div>
                    <div className="flex gap-3 p-4 bg-amber-50 dark:bg-amber-950/30 rounded-2xl border border-amber-100 dark:border-amber-900/40">
                        <AlertCircle size={16} className="text-amber-600 shrink-0 mt-0.5" />
                        <p className="text-xs text-amber-700 dark:text-amber-400">
                            Антиплагиат запускается отдельно для каждой задачи. Дубли посылок одного участника на ту же задачу дедуплицируются — используется только последняя попытка.
                            Пары одного участника никогда не сравниваются.
                        </p>
                    </div>
                </div>
            </div>

        </div>
    );
};
