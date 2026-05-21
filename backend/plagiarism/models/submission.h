#pragma once
#include <string>
#include "programming_language.h"

/// @brief Raw input record representing one competitive-programming submission.
struct Submission {
    std::string id;
    ProgrammingLanguage language = ProgrammingLanguage::Unknown;
    std::string rawCode;
    std::string participant;
    std::string problem;
    std::string file_name;
    std::string source_path;
};