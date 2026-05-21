#pragma once

#include <cstdint>
#include <unordered_map>
#include <string>
#include <vector>

#include "token.h"
#include "token_features.h"
#include "winnowing_features.h"
#include "../ast/ast_features.h"

/// @brief All derived features computed from a single submission's source code.
struct SubmissionData {
    std::string submission_id;

    std::string raw_code;
    std::string ast_code;
    std::string token_code;
    std::string ir_code;
    bool ir_parse_ok = false;

    std::vector<Token> tokens;
    std::vector<Token> normalized_tokens;
    std::vector<std::string> normalized_token_texts;
    WinnowingFeatures winnowing_features;
    TokenFeatures token_features;
    AstFeatures ast_features;

    std::unordered_map<std::uint64_t, int> ast_subtree_hash_freq;
    std::vector<std::string> ast_normalized_sequence;
};