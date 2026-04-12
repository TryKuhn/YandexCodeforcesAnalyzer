#pragma once

#include <string>
#include <vector>

#include "token.h"
#include "token_features.h"
#include "winnowing_features.h"
#include "../ast/ast_features.h"

struct SubmissionData {
    int submission_id = 0;

    std::string raw_code;
    std::string ast_code;
    std::string token_code;

    std::vector<Token> tokens;
    std::vector<Token> normalized_tokens;
    std::vector<std::string> normalized_token_texts;
    WinnowingFeatures winnowing_features;
    TokenFeatures token_features;
    AstFeatures ast_features;
};