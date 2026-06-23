import { Link } from 'react-router-dom';
import {
    Globe, ShieldCheck, BarChart3, Sparkles, ArrowLeft,
    KeyRound, Bot, FolderTree, TestTube, Package, FileText,
    Wrench, RefreshCw, Code2, ListChecks, AlertTriangle, CheckCircle2,
} from 'lucide-react';
import { TaskForgeIcon } from '../components/TaskForgeLogo';
import { ThemeToggle } from '../components/ThemeToggle';
import { SiteFooter } from '../components/SiteFooter';

// ─── Small building blocks ───────────────────────────────────────────────────

const Section = ({ id, icon: Icon, title, children }: any) => (
    <section id={id} className="scroll-mt-24">
        <div className="flex items-center gap-3 mb-5">
            <div className="w-11 h-11 shrink-0 bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-900/30 dark:to-fuchsia-900/30 text-violet-600 dark:text-fuchsia-400 rounded-xl flex items-center justify-center">
                <Icon size={22} />
            </div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">{title}</h2>
        </div>
        <div className="space-y-4 text-slate-600 dark:text-slate-300 leading-relaxed text-[15px]">
            {children}
        </div>
    </section>
);

const SubHeading = ({ icon: Icon, children, anchor }: any) => (
    <h3
        id={anchor}
        className="scroll-mt-24 text-lg font-bold text-slate-800 dark:text-white pt-4 flex items-center gap-2"
    >
        {Icon && <Icon size={18} className="text-violet-500" />}
        {children}
    </h3>
);

const Step = ({ n, title, children }: any) => (
    <div className="flex gap-4">
        <div className="w-7 h-7 shrink-0 mt-0.5 bg-gradient-to-br from-violet-600 to-fuchsia-500 text-white rounded-full flex items-center justify-center font-bold text-sm shadow shadow-violet-500/30">
            {n}
        </div>
        <div className="flex-1">
            <p className="font-bold text-slate-800 dark:text-white mb-1">{title}</p>
            <div className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed space-y-1">{children}</div>
        </div>
    </div>
);

const Card = ({ children }: any) => (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 p-5 sm:p-7 shadow-sm space-y-5">
        {children}
    </div>
);

const Note = ({ children, danger }: any) => (
    <div className={`rounded-xl p-4 text-sm leading-relaxed border ${
        danger
            ? 'bg-red-50 dark:bg-red-900/20 border-red-100 dark:border-red-800/30 text-red-700 dark:text-red-400'
            : 'bg-amber-50 dark:bg-amber-900/20 border-amber-100 dark:border-amber-800/30 text-amber-700 dark:text-amber-400'
    }`}>
        {children}
    </div>
);

const Term = ({ children }: any) => (
    <span className="font-mono text-[13px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 px-1.5 py-0.5 rounded">
        {children}
    </span>
);

// File-taxonomy row.
const FileRow = ({ file, title, children }: any) => (
    <div className="flex flex-col sm:flex-row gap-1 sm:gap-4 py-2.5 border-b border-slate-100 dark:border-slate-800 last:border-0">
        <div className="sm:w-44 shrink-0">
            <Term>{file}</Term>
        </div>
        <div className="text-sm text-slate-600 dark:text-slate-400">
            <b className="text-slate-700 dark:text-slate-300">{title}.</b> {children}
        </div>
    </div>
);

const TOC_ITEMS = [
    { href: '#import',      label: 'Импорт результатов' },
    { href: '#plagiarism',  label: 'Антиплагиат' },
    { href: '#analytics',   label: 'Аналитика' },
    { href: '#polygon',     label: 'Задачи на Polygon' },
    { href: '#polygon-prep',     label: '— Подготовка', sub: true },
    { href: '#polygon-types',    label: '— Тип задачи', sub: true },
    { href: '#polygon-statement', label: '— Вкладка «Условие»', sub: true },
    { href: '#polygon-files',    label: '— Вкладка «Файлы»', sub: true },
    { href: '#polygon-tests',    label: '— Вкладка «Тесты»', sub: true },
    { href: '#polygon-ai',       label: '— ИИ-ассистент', sub: true },
    { href: '#polygon-build',    label: '— Вкладка «Пакеты»', sub: true },
    { href: '#polygon-flow',     label: '— Сквозной сценарий', sub: true },
    { href: '#polygon-faq',      label: '— Частые проблемы', sub: true },
];

// ─── Page ────────────────────────────────────────────────────────────────────

export const Docs = () => {
    return (
        <div className="min-h-screen w-full bg-slate-100 dark:bg-slate-950 transition-colors duration-300 flex flex-col">
            {/* Top nav */}
            <nav className="w-full border-b border-slate-100 dark:border-slate-800 sticky top-0 bg-slate-100/80 dark:bg-slate-900/80 backdrop-blur-md z-50">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex justify-between items-center">
                    <Link to="/" className="flex items-center gap-2 font-bold text-xl text-slate-900 dark:text-white">
                        <TaskForgeIcon size={36} className="shrink-0" />
                        <span>TaskForge</span>
                    </Link>
                    <div className="flex items-center gap-4 sm:gap-6">
                        <ThemeToggle />
                        <Link
                            to="/"
                            className="flex items-center gap-1.5 font-medium text-slate-600 dark:text-slate-400 hover:text-violet-600 dark:hover:text-fuchsia-400 transition-colors text-sm"
                        >
                            <ArrowLeft size={16} /> На главную
                        </Link>
                    </div>
                </div>
            </nav>

            <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-6 py-10 sm:py-14">
                {/* Hero */}
                <div className="mb-12">
                    <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 dark:text-white tracking-tight mb-4">
                        Документация
                    </h1>
                    <p className="text-base sm:text-lg text-slate-600 dark:text-slate-400 max-w-3xl leading-relaxed">
                        TaskForge объединяет импорт результатов контестов с Codeforces и Yandex,
                        встроенный антиплагиат, аналитику успеваемости и создание задач на Polygon
                        с помощью ИИ. Ниже — полное описание каждого инструмента.
                    </p>
                </div>

                <div className="lg:grid lg:grid-cols-[230px_1fr] lg:gap-12">
                    {/* TOC */}
                    <aside className="hidden lg:block">
                        <div className="sticky top-24">
                            <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Содержание</p>
                            <nav className="space-y-0.5">
                                {TOC_ITEMS.map(item => (
                                    <a
                                        key={item.href}
                                        href={item.href}
                                        className={`block px-3 py-1.5 rounded-lg text-sm hover:bg-white dark:hover:bg-slate-900 hover:text-violet-600 dark:hover:text-fuchsia-400 transition-colors ${
                                            item.sub
                                                ? 'pl-6 text-[13px] text-slate-400 dark:text-slate-500'
                                                : 'text-slate-500 dark:text-slate-400'
                                        }`}
                                    >
                                        {item.label}
                                    </a>
                                ))}
                            </nav>
                        </div>
                    </aside>

                    {/* Content */}
                    <div className="space-y-16 min-w-0">

                        {/* ─── Импорт ─── */}
                        <Section id="import" icon={Globe} title="Импорт результатов контеста">
                            <p>
                                Раздел <b>Соревнования → Загрузить</b> переносит таблицу результатов и коды
                                посылок из внешней системы в TaskForge. Поддерживаются <b>Codeforces</b>
                                {' '}(по API-ключу и секрету) и <b>Yandex Contest</b> (по OAuth-токену).
                                Ключи и токены задаются в <Link to="/profile" className="text-violet-600 dark:text-fuchsia-400 underline underline-offset-2">профиле</Link>.
                            </p>
                            <Card>
                                <Step n="1" title="Выберите платформу">
                                    Codeforces или Yandex — переключатель вверху формы.
                                </Step>
                                <Step n="2" title="Укажите ID контеста">
                                    Числовой идентификатор соревнования из адресной строки на платформе.
                                </Step>
                                <Step n="3" title="Задайте диапазон строк">
                                    <p><Term>Начиная с позиции</Term> и <Term>Количество строк</Term> ограничивают
                                    выгружаемый фрагмент таблицы — удобно для очень больших контестов.</p>
                                </Step>
                                <Step n="4" title="Настройте режимы">
                                    <p><b>Режим менеджера</b> — доступ к кодам посылок и расширенным данным
                                    (обязателен для приватных тренировок Codeforces).</p>
                                    <p><b>Вне конкурса</b> — включить неофициальных участников в таблицу.</p>
                                </Step>
                                <Step n="5" title="Запустите импорт">
                                    После загрузки контест появится в списке <b>Соревнования</b>.
                                </Step>
                            </Card>
                            <Note>
                                Для приватных тренировок Codeforces без режима менеджера коды посылок
                                недоступны, а значит не сработает и антиплагиат.
                            </Note>
                        </Section>

                        {/* ─── Антиплагиат ─── */}
                        <Section id="plagiarism" icon={ShieldCheck} title="Антиплагиат">
                            <p>
                                Проверка запускается из контеста: <b>Аналитика → Проверка на плагиат</b>.
                                Сравнение кода выполняет нативный C++-модуль на основе LSH-хэширования,
                                поэтому проверка устойчива к переименованиям и перестановкам и работает
                                быстро даже на больших объёмах посылок.
                            </p>
                            <Card>
                                <Step n="1" title="Порог отображения">
                                    Пары с совпадением ≥ этого порога попадают в отчёт для ручной проверки.
                                </Step>
                                <Step n="2" title="Порог автобана">
                                    <p>Пары с совпадением ≥ этого порога автоматически получают 0 баллов.
                                    Должен быть не ниже порога отображения.</p>
                                </Step>
                                <Step n="3" title="Фильтры">
                                    <p><b>Только успешные решения</b> — игнорировать посылки с WA, TL, RE и т.д.
                                    Дополнительно можно ограничить проверку конкретными языками и задачами.</p>
                                </Step>
                                <Step n="4" title="Отчёт и ручная проверка">
                                    <p>В отчёте подозрительные пары отсортированы по проценту совпадения.
                                    Каждую пару можно открыть в режиме сравнения «бок о бок» с подсветкой
                                    совпадающих фрагментов и принять решение вручную.</p>
                                </Step>
                                <Step n="5" title="Скорректированная таблица">
                                    Результаты автобана и ручных решений учитываются в итоговой таблице контеста.
                                </Step>
                            </Card>
                        </Section>

                        {/* ─── Аналитика ─── */}
                        <Section id="analytics" icon={BarChart3} title="Аналитика">
                            <p>
                                Для каждого контеста доступны таблица результатов, просмотр исходного кода
                                любой посылки и визуальная аналитика: распределение баллов, активность по
                                времени, выявление аномалий и рейтинги участников. Эти данные помогают
                                быстро оценить контест и точечно проверить подозрительные результаты.
                            </p>
                        </Section>

                        {/* ─── Polygon ─── */}
                        <Section id="polygon" icon={Sparkles} title="Создание задач на Polygon с ИИ">
                            <p>
                                <a href="https://polygon.codeforces.com" target="_blank" rel="noopener noreferrer" className="text-violet-600 dark:text-fuchsia-400 underline underline-offset-2">Polygon</a>
                                {' '}— это система подготовки задач Codeforces. TaskForge работает
                                <b> напрямую с вашим аккаунтом Polygon</b>: всё, что вы меняете во вкладках
                                задачи, сразу сохраняется и коммитится в Polygon, а ИИ-ассистент помогает
                                написать условие, генератор, валидатор, чекер, решения и тесты — и собрать
                                готовый пакет с автоматической починкой ошибок сборки.
                            </p>
                            <p>
                                Под каждой задачей в фоне живёт <b>ИИ-сессия</b>: она хранит выбранную модель,
                                тип задачи, историю чата и контекст файлов. При открытии задачи актуальное
                                состояние из Polygon автоматически подтягивается в сессию, чтобы ассистент
                                работал с реальным содержимым.
                            </p>

                            {/* Подготовка */}
                            <SubHeading icon={KeyRound} anchor="polygon-prep">Подготовка</SubHeading>
                            <Card>
                                <Step n="1" title="Привяжите Polygon API">
                                    <p>В <Link to="/profile" className="text-violet-600 dark:text-fuchsia-400 underline underline-offset-2">профиле</Link>
                                    {' '}→ <b>Интеграции → Polygon</b> укажите <Term>API KEY</Term> и
                                    {' '}<Term>API SECRET</Term>. Ключи создаются на Polygon в разделе
                                    {' '}<i>Settings → API keys</i>. Без них список задач недоступен.</p>
                                </Step>
                                <Step n="2" title="Создайте задачу">
                                    <p>Раздел <b>Задачи → «+ Задача»</b>. Введите системное имя на латинице
                                    (например <Term>a-plus-b</Term>) — в вашем Polygon будет создана новая
                                    задача, а TaskForge откроет её рабочий стол.</p>
                                </Step>
                                <Step n="3" title="Проверьте права доступа">
                                    <p>Задачи с доступом <Term>READ</Term> можно только просматривать. Для
                                    редактирования и сборки нужен доступ <Term>WRITE</Term> или <Term>OWNER</Term>
                                    {' '}(бейдж виден в списке задач).</p>
                                </Step>
                            </Card>

                            {/* Тип задачи */}
                            <SubHeading icon={ListChecks} anchor="polygon-types">Тип задачи</SubHeading>
                            <p>
                                В шапке задачи переключается тип — он определяет, какие файлы нужны и как
                                задача проверяется. Сменить тип можно в любой момент.
                            </p>
                            <ul className="space-y-2.5">
                                <li className="bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-4">
                                    <b className="dark:text-white">Обычная (regular).</b> Классическая задача:
                                    участник печатает ответ, его проверяет <Term>checker</Term>. Набор файлов:
                                    валидатор, генератор, скрипт тестов, чекер, решения.
                                </li>
                                <li className="bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-4">
                                    <b className="dark:text-white">Интерактивная (interactive).</b> Добавляется
                                    {' '}<Term>interactor</Term>: программа участника общается с интерактором
                                    через stdin/stdout в реальном времени. В условии появляется блок
                                    {' '}<i>Протокол взаимодействия</i>, чекер работает в интерактивном режиме.
                                </li>
                                <li className="bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-4">
                                    <b className="dark:text-white">Output-only.</b> Участник сдаёт не код, а
                                    готовые ответы. Оценивает <Term>scorer</Term> (ставится на Polygon как
                                    checker) с частичными баллами через <Term>{'quitp(...)'}</Term>; эталонные
                                    ответы (<Term>*.a</Term>) получаются прогоном основного решения. Баллы
                                    включаются автоматически.
                                </li>
                            </ul>

                            {/* Обзор вкладок */}
                            <SubHeading icon={FolderTree}>Рабочий стол задачи</SubHeading>
                            <p>
                                Слева — четыре вкладки с содержимым задачи, справа — чат с ИИ-ассистентом
                                (его панель можно растягивать). Любая правка во вкладке или ответ ассистента
                                синхронизируются с Polygon.
                            </p>
                            <div className="grid sm:grid-cols-2 gap-3">
                                <div className="flex gap-3 bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-4">
                                    <FileText size={18} className="text-blue-500 shrink-0 mt-0.5" />
                                    <p className="text-sm"><b>Условие</b> — легенда, ввод/вывод, примечания,
                                    примеры, теги, оценивание; превью LaTeX.</p>
                                </div>
                                <div className="flex gap-3 bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-4">
                                    <FolderTree size={18} className="text-blue-500 shrink-0 mt-0.5" />
                                    <p className="text-sm"><b>Файлы</b> — исходники и скрипт тестов; правки
                                    сохраняются в Polygon.</p>
                                </div>
                                <div className="flex gap-3 bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-4">
                                    <TestTube size={18} className="text-blue-500 shrink-0 mt-0.5" />
                                    <p className="text-sm"><b>Тесты</b> — скрипт генерации и список тестов;
                                    просмотр входа/выхода каждого теста.</p>
                                </div>
                                <div className="flex gap-3 bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-4">
                                    <Package size={18} className="text-blue-500 shrink-0 mt-0.5" />
                                    <p className="text-sm"><b>Пакеты</b> — сборка финального пакета с
                                    ИИ-починкой ошибок.</p>
                                </div>
                            </div>

                            {/* Условие */}
                            <SubHeading icon={FileText} anchor="polygon-statement">Вкладка «Условие»</SubHeading>
                            <p>
                                Редактируются все части условия: <b>название</b>, <b>легенда</b>,
                                {' '}<b>формат ввода</b>, <b>формат вывода</b>, <b>примечания</b>. Форматирование —
                                в <b>LaTeX</b> (математика в <Term>$...$</Term>), рядом отрисовывается живое
                                превью, как задача будет выглядеть на Codeforces.
                            </p>
                            <ul className="list-disc pl-5 space-y-1.5 text-sm">
                                <li><b>Примеры.</b> Пары вход/выход, которые показываются в условии.</li>
                                <li><b>Теги.</b> Чипы тем; добавляются и удаляются с моментальным сохранением.
                                    Кнопка <b>«ИИ-теги»</b> предлагает теги по условию.</li>
                                <li><b>Оценивание.</b> Для задач с группами/баллами — блок scoring; его можно
                                    сгенерировать ИИ под выбранную схему.</li>
                                <li><b>Протокол взаимодействия.</b> Появляется для интерактивных задач —
                                    описание диалога участника с интерактором.</li>
                            </ul>
                            <p>
                                Условие можно надиктовать ассистенту: переключите контекст чата на
                                {' '}<b>Условие</b> и попросите «составь условие по описанию: …» — он заполнит
                                поля и синхронизирует их с Polygon.
                            </p>

                            {/* Файлы */}
                            <SubHeading icon={Code2} anchor="polygon-files">Вкладка «Файлы»</SubHeading>
                            <p>Технические файлы задачи. Каждый сохраняется в Polygon в правильную категорию:</p>
                            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 p-5">
                                <FileRow file="validator.cpp" title="Валидатор">
                                    проверяет, что вход корректен и не нарушает ограничений (testlib
                                    {' '}<Term>registerValidation</Term>).
                                </FileRow>
                                <FileRow file="generator.cpp" title="Генератор">
                                    печатает один тест по именованным параметрам
                                    {' '}<Term>{'opt<T>("имя")'}</Term> (testlib <Term>{'registerGen(argc,argv,1)'}</Term>).
                                </FileRow>
                                <FileRow file="script.txt" title="Скрипт тестов">
                                    FreeMarker-скрипт, который много раз вызывает генератор с разными
                                    параметрами, формируя набор тестов.
                                </FileRow>
                                <FileRow file="checker.cpp" title="Чекер">
                                    сравнивает вывод участника с эталоном (testlib <Term>registerTestlibCmd</Term>).
                                </FileRow>
                                <FileRow file="interactor.cpp" title="Интерактор">
                                    только для интерактивных задач — ведёт диалог с решением участника.
                                </FileRow>
                                <FileRow file="solution.cpp / .py" title="Основное решение">
                                    эталонное верное решение (тег <Term>MA</Term>); на нём строятся ответы тестов.
                                </FileRow>
                                <FileRow file="wa / tl / re / ml" title="Неверные решения">
                                    решения, которые должны падать с WA / TL / RE / ML — для проверки тестов и
                                    ограничений.
                                </FileRow>
                                <FileRow file="scorer.cpp / jury.cpp" title="Output-only">
                                    скорер с частичными баллами и решатель-эталон для ответов
                                    (<Term>*.a</Term>).
                                </FileRow>
                            </div>
                            <p>
                                Файлы открываются в редакторе и сохраняются прямо в Polygon. Доступна
                                {' '}<b>двусторонняя синхронизация</b>: кнопка <b>«Подтянуть из Polygon»</b>
                                {' '}загружает текущее содержимое задачи из Polygon в ИИ-сессию (если вы
                                редактировали задачу вне TaskForge), а правки из TaskForge уходят в Polygon
                                одним коммитом.
                            </p>

                            {/* Тесты */}
                            <SubHeading icon={TestTube} anchor="polygon-tests">Вкладка «Тесты»</SubHeading>
                            <p>
                                Вверху — <b>скрипт генерации тестов</b> (FreeMarker), его можно
                                редактировать и сохранять. Ниже — список тестов: для каждого видны бейджи
                                (ручной / из генератора / группа / баллы / пример) и строка вызова генератора.
                                По кнопкам <b>Вход</b> и <b>Выход</b> открывается полноэкранный просмотр
                                данных теста (вывод считается на стороне Polygon прогоном решения, поэтому
                                может занять несколько секунд).
                            </p>
                            <Note>
                                <b>Согласованность генератора и скрипта.</b> Скрипт обязан передавать
                                {' '}генератору <i>ровно те</i> именованные ключи, которые тот читает через
                                {' '}<Term>{'opt<T>("имя")'}</Term>. Лишний ключ (например <Term>--seed</Term>,
                                {' '}который генератор не читает) приводит к ошибке testlib
                                {' '}<Term>unused key</Term>. Поэтому ИИ сначала продумывает <i>план тестов</i>
                                {' '}(единый набор параметров и нужен ли <Term>seed</Term>), а затем генерирует
                                генератор и скрипт согласованно. <Term>seed</Term> уместен, когда нужно
                                несколько <i>разных</i> случайных тестов с одинаковыми параметрами.
                            </Note>

                            {/* ИИ-ассистент */}
                            <SubHeading icon={Bot} anchor="polygon-ai">ИИ-ассистент</SubHeading>
                            <p>
                                Чат справа от вкладок. Вверху выбирается <b>модель</b> (Claude Opus 4.8,
                                Claude Sonnet 4.6, Gemini 3.1 Pro, GPT-5.5 Pro) и <b>контекст</b>, в котором
                                работает ассистент:
                            </p>
                            <ul className="list-disc pl-5 space-y-1.5 text-sm">
                                <li><b>Вся задача</b> — ассистент видит условие и все файлы целиком.</li>
                                <li><b>Условие</b> — работа над текстом задачи.</li>
                                <li><b>Конкретный файл</b> — генератор, валидатор, чекер, интерактор, скорер,
                                    скрипт тестов или одно из решений (main C++, Python OK, TL, WA, RE, ML).
                                    Запросить генерацию ещё не существующего файла можно — он будет создан с нуля.</li>
                            </ul>
                            <p>Ассистент умеет три типа действий:</p>
                            <ul className="list-disc pl-5 space-y-1.5 text-sm">
                                <li><b>Создать / изменить</b> файл или условие — результат сразу пишется в Polygon,
                                    под сообщением появляется бейдж <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400"><RefreshCw size={11}/> Синхронизировано с Polygon</span>.</li>
                                <li><b>Ответить на вопрос</b> по задаче — без изменений файлов (объяснить алгоритм,
                                    предложить тесты, найти ошибку).</li>
                                <li>При изменении условия ассистент при необходимости перегенерирует <b>зависимые
                                    файлы</b>, чтобы они остались согласованными.</li>
                            </ul>
                            <Note>
                                Весь генерируемый код пишется с комментариями и строками только на
                                <b> английском (ASCII)</b>: кириллица в исходниках ломает кодировку файлов на
                                Polygon.
                            </Note>

                            {/* Пакеты */}
                            <SubHeading icon={Package} anchor="polygon-build">Вкладка «Пакеты» и ИИ-починка</SubHeading>
                            <p>
                                Кнопка <b>«Собрать (с ИИ-починкой)»</b> запускает сборку пакета. Когда задача
                                ведётся через ИИ-сессию, сборка идёт по цикле авто-ремонта:
                            </p>
                            <Card>
                                <Step n="1" title="Сборка и опрос статуса">
                                    Пакет коммитится и собирается; статус опрашивается до <Term>READY</Term> или
                                    {' '}<Term>FAILED</Term>.
                                </Step>
                                <Step n="2" title="Поиск виновного файла">
                                    При ошибке из лога определяется, в каком файле проблема (генератор, чекер,
                                    валидатор и т.д.).
                                </Step>
                                <Step n="3" title="Починка (до 3 попыток на файл)">
                                    <p>ИИ исправляет этот файл и пересобирает. В баннере виден шаг вроде
                                    {' '}<i>«Ошибка в checker, ИИ исправляет (попытка 2/3)»</i>. При ошибке
                                    рассогласования генератора и скрипта в контекст починки подаётся и
                                    <b> связанный файл</b>, чтобы свести параметры.</p>
                                </Step>
                                <Step n="4" title="Результат">
                                    <p>Успех — статус <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400"><CheckCircle2 size={12}/> Пакет собран</span>.
                                    Если за отведённые попытки починить не удалось — статус
                                    {' '}<span className="inline-flex items-center gap-1 text-red-600 dark:text-red-400"><Wrench size={12}/> Не удалось собрать автоматически</span>
                                    {' '}с исходным текстом ошибки для ручного вмешательства.</p>
                                </Step>
                            </Card>
                            <p className="text-sm text-slate-500">
                                Каждый пакет в списке показывает ревизию, время и статус
                                (<Term>В очереди</Term> / <Term>Сборка</Term> / <Term>Готов</Term> /
                                {' '}<Term>Ошибка</Term>); текст ошибки сборки выводится полностью. Скачивание
                                собранных пакетов пока в разработке.
                            </p>

                            {/* Сквозной сценарий */}
                            <SubHeading icon={Sparkles} anchor="polygon-flow">Рекомендуемый сквозной сценарий</SubHeading>
                            <Card>
                                <Step n="1" title="Создайте задачу и выберите тип">
                                    Задачи → «+ Задача», затем в шапке укажите обычная / интерактивная / output-only.
                                </Step>
                                <Step n="2" title="Сформируйте условие">
                                    Контекст <b>Условие</b> → «составь условие по описанию: …», проверьте превью
                                    LaTeX, добавьте примеры и теги.
                                </Step>
                                <Step n="3" title="Сгенерируйте файлы">
                                    Контекст <b>Вся задача</b> → «напиши валидатор, генератор, скрипт тестов,
                                    чекер и основное решение». ИИ продумает план тестов и сделает генератор со
                                    скриптом согласованными.
                                </Step>
                                <Step n="4" title="Проверьте тесты">
                                    Вкладка <b>Тесты</b>: просмотрите входы и выходы, при необходимости
                                    попросите добавить граничные/стрессовые случаи.
                                </Step>
                                <Step n="5" title="Соберите пакет">
                                    Вкладка <b>Пакеты</b> → «Собрать (с ИИ-починкой)». Дождитесь статуса
                                    «Пакет собран»; при остановке на ручной починке исправьте указанный файл и
                                    соберите снова.
                                </Step>
                            </Card>

                            {/* FAQ */}
                            <SubHeading icon={AlertTriangle} anchor="polygon-faq">Частые проблемы</SubHeading>
                            <ul className="space-y-3">
                                <li className="bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-4 text-sm">
                                    <b className="dark:text-white">«unused key 'seed'» при генерации тестов.</b>
                                    {' '}Скрипт передаёт ключ, который генератор не читает. Решение: либо убрать
                                    ключ из скрипта, либо добавить его чтение в генератор. ИИ-починка делает это
                                    сама, если запустить сборку.
                                </li>
                                <li className="bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-4 text-sm">
                                    <b className="dark:text-white">Сломанная кодировка в файле.</b> В исходниках
                                    не должно быть кириллицы — только ASCII-комментарии и строки.
                                </li>
                                <li className="bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-4 text-sm">
                                    <b className="dark:text-white">Список задач недоступен / 403.</b> Не привязан
                                    или неверен Polygon API — проверьте ключи в профиле, а также права доступа к
                                    конкретной задаче.
                                </li>
                                <li className="bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-4 text-sm">
                                    <b className="dark:text-white">Output-only: нет ответов.</b> Ответы
                                    {' '}(<Term>*.a</Term>) создаются прогоном основного решения (тег
                                    {' '}<Term>MA</Term>) при сборке — убедитесь, что оно добавлено и корректно.
                                </li>
                            </ul>
                        </Section>
                    </div>
                </div>
            </main>

            <SiteFooter />
        </div>
    );
};
