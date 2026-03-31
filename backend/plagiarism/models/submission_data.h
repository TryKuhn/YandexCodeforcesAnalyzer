#pragma once
#include<string>
#include <vector>

#include "token.h"

struct SubmissionData {
    std::string rawCode;

    std::string astCode;
    std::string preprocessedCode;

    std::vector<Token> ppTokens;
    std::vector<Token> normalizedPpTokens;
    std::vector<std::string> normalizedPpTokenTexts;

    TokenFeatures tokenFeatures;
    AstFeatures astFeatures;
    PreprocessorFeatures ppFeatures;
};