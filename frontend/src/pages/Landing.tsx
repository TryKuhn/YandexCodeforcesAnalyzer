import { Link } from 'react-router-dom';
import {ShieldCheck, BarChart3, Globe, Cpu, FileSpreadsheet, Sparkles} from 'lucide-react';
import {ThemeToggle} from "../components/ThemeToggle.tsx";

const FeatureCard = ({ icon: Icon, title, description }: any) => (
    <div className="bg-white dark:bg-slate-400 p-8 md:p-8 rounded-2xl border border-slate-100 dark:border-slate-300 shadow-sm
    hover:shadow-md transition-all">
        <div className="w-12 h-12 bg-blue-50 dark: bg-blue-100 text-blue-600 rounded-xl flex items-center justify-center mb-6">
            <Icon size={24} />
        </div>
        <h3 className="text-xl font-bold text-slate-900 mb-3">{title}</h3>
        <p className="text-slate-600 leading-relaxed text-sm md:text-base">{description}</p>
    </div>
);

const Step = ({ number, title, description }: any) => (
    <div className="flex flex-col items-center text-center px-4">
        <div className="w-10 h-10 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold mb-4 shadow-lg">
            {number}
        </div>
        <h4 className="font-bold text-lg mb-2 dark:text-white">{title}</h4>
        <p className="text-slate-500 dark:text-slate-400 text-sm leading-relaxed">{description}</p>
    </div>
);

export const Landing = () => {
    return (
        <div className="min-h-screen w-full bg-slate-100 dark:bg-gray-900 transition-colors duration-300">
            <nav className="w-full border-b border-slate-100 dark:border-slate-800 sticky top-0 bg-slate-100/80 dark:bg-slate-900/80 backdrop-blur-md z-50">
                <div className="max-w-7xl mx-auto px-6 py-6 flex justify-between items-center">
                    <div className="flex items-center gap-2 font-bold text-2xl text-slate-900 dark:text-white">
                        <div className="w-12 h-12 bg-blue-600 dark:bg-blue-500 rounded-lg flex items-center justify-center text-white shadow-lg">MC</div>
                        Менеджмент контестов
                    </div>
                    <div className="flex items-center gap-8">
                        <ThemeToggle />
                        <Link to="/login" className="font-medium text-slate-600 dark:text-slate-400 hover:text-blue-600">Войти</Link>
                        <Link to="/register" className="bg-slate-900 dark:bg-white dark:text-slate-900 text-white px-6 py-2.5 rounded-full font-medium hover:opacity-90">Регистрация</Link>
                    </div>
                </div>
            </nav>

            <header className="w-full px-6 pt-20 pb-32">
                <div className="max-w-4xl mx-auto text-center">
                    <h1 className="text-5xl md:text-7xl font-extrabold text-slate-900 dark:text-white tracking-tight mb-8">
                        Система управления <span className="text-blue-600 dark:text-blue-500">контестами</span>
                    </h1>
                    <p className="text-xl text-slate-600 dark:text-slate-400 leading-relaxed">
                        Автоматизированный сбор результатов и посылок с Codeforces и Yandex,
                        встроенный антиплагиат и аналитика успеваемости учащихся.
                    </p>
                </div>
            </header>

            <section className="w-full bg-slate-50 dark:bg-slate-800/50 py-32 border-y border-slate-100 dark:border-slate-800">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                        <FeatureCard
                            icon={Globe}
                            title="Мультиплатформенность"
                            description="Импорт результатов и кодов посылок напрямую из API Codeforces и Yandex Contest в пару кликов."
                        />
                        <FeatureCard
                            icon={ShieldCheck}
                            title="Антиплагиат"
                            description="Умное сравнение кода с возможностью ручной проверки подозрительных пар посылок."
                        />
                        <FeatureCard
                            icon={BarChart3}
                            title="Аналитика"
                            description="Визуализация результатов контеста, нахождение подозрительных, рейтинги, таблицы."
                        />
                        <FeatureCard
                            icon={Sparkles}
                            title="AI Генерация задач"
                            description="Автоматическое создание условий, чекеров и тестов через ИИ с прямой выгрузкой в Polygon."
                        />
                    </div>
                </div>
            </section>

            <section className="w-full py-32 bg-white dark:bg-slate-900">
                <div className="max-w-7xl mx-auto px-6 text-center">
                    <h2 className="text-3xl md:text-4xl font-bold text-slate-900 dark:text-white mb-16">Всего три шага до результата</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-12 relative">
                        <div className="hidden md:block absolute top-5 left-1/4 right-1/4 h-0.5 bg-slate-100 dark:bg-slate-800 z-0"></div>

                        <div className="relative z-10"><Step number="1" title="Импорт" description="Укажите ID контеста на Codeforces или Yandex и параметры выгрузки." icon={Globe} /></div>
                        <div className="relative z-10"><Step number="2" title="Проверка" description="Просмотрите посылки и результаты, при необходимости запустите антиплагиат." icon={Cpu} /></div>
                        <div className="relative z-10"><Step number="3" title="Анализ" description="Просмотрите отчёты о результатах и отчёты антиплагиата и получите скорректированную таблицу." icon={FileSpreadsheet} /></div>
                    </div>
                </div>
            </section>

            <footer className="w-full py-12 border-t border-slate-100 dark:border-slate-800 text-center">
                <p className="text-slate-400 dark:text-slate-500 text-sm mb-4">
                    © {new Date().getFullYear()} Contest Manager System.
                </p>
                <div className="flex justify-center gap-6 text-slate-400 text-sm">
                    <a href="/docs" className="hover:text-blue-600 transition-colors">Документация</a>
                    <a href="https://github.com/TryKuhn/YandexCodeforcesAnalyzer" className="hover:text-blue-600 transition-colors">GitHub</a>
                </div>
            </footer>
        </div>
    );
};