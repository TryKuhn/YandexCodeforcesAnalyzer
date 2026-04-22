#pragma once

#include "token_features.h"
#include "../ast/ast_features.h"
#include "preprocessor_features.h"

struct SubmissionFeatures {
    TokenFeatures token;
    AstFeatures ast;
    PreprocessorFeatures pp;
};