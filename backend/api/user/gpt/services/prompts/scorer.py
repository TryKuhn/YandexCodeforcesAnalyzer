"""Prompt for generating a checker-scorer (output-only / partial scoring).

Conventions follow the project's canonical scorer example (see SCORER_EXAMPLE):
the jury's optimal objective is embedded in the input file and read via `inf`;
the participant answer is read and structurally validated from `ouf` using
`ouf.readLong/readInt(lo, hi, "name")` + `ouf.quitif(cond, _wa, "msg")`; partial
points are awarded with `quitp(<double points>, "msg")` (absolute points, full
for an optimal answer), so the testing system runs all tests and sums scores.
"""
from .base import NO_FENCES, TESTLIB_INTRO

SCORER_EXAMPLE = r'''#include "testlib.h"

#define int int64_t
using namespace std;

double score(int p_ans, int j_ans) {
    double v = (double(p_ans) / double(j_ans)) * 10.0;   // 10.0 = max points of the test
    return ceil(v * 100.0 - 1e-12) / 100.0;
}

int w, n, m;
// ... problem-specific jury data read from inf ...

int inputAndValidateAnswer(InStream& stream) {
    int k = stream.readLong(1, n, "k");
    set<int> use;
    vector<int> vertex(k);
    for (int i = 0; i < k; ++i) {
        vertex[i] = stream.readLong(1, n, "v[" + to_string(i) + "]") - 1;
        stream.quitif(use.count(vertex[i]), _wa, "There is a cycle!");
        use.insert(vertex[i]);
    }
    // ... compute participant objective, quitif on any constraint violation ...
    return /* participant objective */ 0;
}

int32_t main(int32_t argc, char* argv[]) {
    registerTestlibCmd(argc, argv);
    int jury_s = inf.readLong();          // jury optimum embedded in the input
    // ... read the rest of the test from inf ...
    int participant_s = inputAndValidateAnswer(ouf);
    if (participant_s >= jury_s)
        quitp(10.0, "Perfect!");
    else
        quitp(score(participant_s, jury_s), "p=" + to_string(participant_s) +
              " jury=" + to_string(jury_s));
}'''

SYSTEM_PROMPT = (
    f"{TESTLIB_INTRO}\n"
    "Напиши чекер-скорер на C++ с testlib.h для OUTPUT-ONLY задачи. "
    "Участник присылает свой ответ, скорер выставляет ЧАСТИЧНЫЕ баллы. Требования:\n"
    "1) registerTestlibCmd(argc, argv).\n"
    "2) Читай тест из inf. Оптимум/ответ жюри, как правило, ЗАШИТ во входной файл — "
    "прочитай его из inf (например, jury = inf.readLong()).\n"
    "3) Читай и СТРУКТУРНО валидируй ответ участника из ouf через "
    "ouf.readLong(lo, hi, \"name\") / ouf.readInt(lo, hi, \"name\"); при любом нарушении "
    "ограничений завершай ouf.quitif(cond, _wa, \"сообщение\").\n"
    "4) Вычисли целевую функцию (objective) ответа участника и сравни с оптимумом жюри.\n"
    "5) Выстави баллы через quitp(<double>, \"...\") — это АБСОЛЮТНЫЕ баллы теста дробью: "
    "полный балл за оптимальный ответ (например quitp(10.0, ...) при максимуме 10), "
    "иначе пропорциональную долю. Используй именно quitp (а не quitf/quit), "
    "чтобы система прогнала все тесты и просуммировала баллы. "
    "Никогда не выдавай больше баллов, чем заслуживает ответ.\n\n"
    "Пример канонического скорера этого проекта (стиль и конвенции — ориентируйся на него):\n"
    f"{SCORER_EXAMPLE}\n\n"
    f"{NO_FENCES}"
)
