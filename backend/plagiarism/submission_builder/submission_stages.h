#pragma once

#include <string>
#include <vector>

#include "../ast/ast_features.h"
#include "../models/submission.h"
#include "../models/token.h"
#include "../models/token_features.h"

std::string BuildSubmissionAstCode(const Submission& submission);
std::string BuildSubmissionTokenCode(const Submission& submission);

std::vector<Token> BuildSubmissionTokens(const std::string& token_code);
std::vector<Token> BuildNormalizedSubmissionTokens(const std::vector<Token>& tokens);
std::vector<std::string> BuildNormalizedTokenTexts(
    const std::vector<Token>& normalized_tokens
);

TokenFeatures BuildSubmissionTokenFeatures(
    const std::vector<Token>& raw_tokens,
    const std::vector<Token>& normalized_tokens
);

AstFeatures BuildSubmissionAstFeatures(const std::string& ast_code);

