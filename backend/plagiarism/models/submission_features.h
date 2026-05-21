#pragma once

#include "token_features.h"
#include "../ast/ast_features.h"
#include "preprocessor_features.h"

/// @brief Combined feature bundle holding token, AST, and preprocessor statistics.
struct SubmissionFeatures {
    TokenFeatures token;
    AstFeatures ast;
    PreprocessorFeatures pp;
};