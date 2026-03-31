#pragma once
#include <string>
#include "programming_language.h"

struct Submission {
    int id = 0;
    ProgrammingLanguage language = ProgrammingLanguage::Unknown;
    std::string rawCode;
};