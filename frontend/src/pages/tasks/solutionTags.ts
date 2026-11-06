// Polygon solution tags (expected verdicts) for the file editor and the files tab.

// Polygon checks every tag on package build: the solution must get exactly this verdict
export const SOLUTION_TAGS: { value: string; label: string; hint: string }[] = [
    { value: 'MA', label: 'MA — главное решение', hint: 'Главное правильное решение (одно на задачу), по нему строятся ответы' },
    { value: 'OK', label: 'OK — корректное', hint: 'Правильное решение: проходит все тесты' },
    { value: 'TO', label: 'TO — верное или TL', hint: 'Верное, но может не успевать: OK или TL. Тег для медленного перебора' },
    { value: 'WA', label: 'WA — неверный ответ', hint: 'Обязано получить WA хотя бы на одном тесте' },
    { value: 'PE', label: 'PE — ошибка формата', hint: 'Обязано получить PE хотя бы на одном тесте' },
    { value: 'TL', label: 'TL — превышение времени', hint: 'Обязано превысить время хотя бы на одном тесте; если везде успевает, сборка упадёт' },
    { value: 'ML', label: 'ML — превышение памяти', hint: 'Обязано превысить память хотя бы на одном тесте' },
    { value: 'TM', label: 'TM — время или память', hint: 'Превышает время или память хотя бы на одном тесте' },
    { value: 'RE', label: 'RE — ошибка исполнения', hint: 'Обязано упасть с ошибкой исполнения хотя бы на одном тесте' },
    { value: 'RJ', label: 'RJ — отклонено', hint: 'Любой неверный вердикт хотя бы на одном тесте' },
    { value: 'NR', label: 'NR — не запускать', hint: 'Не запускается при сборке пакета (черновик)' },
];

export const SOLUTION_TAG_HINTS: Record<string, string> = Object.fromEntries(
    SOLUTION_TAGS.map(t => [t.value, `${t.label}. ${t.hint}`]),
);
