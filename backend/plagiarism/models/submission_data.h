#pragma once

#include <string>
#include <vector>

#include "token.h"
#include "token_features.h"
#include "../ast/ast_features.h"

struct SubmissionData {
    std::string raw_code;
    std::string ast_code;
    std::string token_code;

    std::vector<Token> tokens;
    std::vector<Token> normalized_tokens;
    std::vector<std::string> normalized_token_texts;

    TokenFeatures token_features;
    AstFeatures ast_features;
};