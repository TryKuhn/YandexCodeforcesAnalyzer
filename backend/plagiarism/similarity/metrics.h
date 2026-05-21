#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

#include "../models/submission_data.h"

double jaccard_score(
    const std::vector<std::string>& lft,
    const std::vector<std::string>& rht
);

double weighted_jaccard_strings(
    const std::vector<std::string>& lft,
    const std::vector<std::string>& rht
);

double cosine_similarity_score(
    const std::unordered_map<std::string, int>& lft,
    const std::unordered_map<std::string, int>& rht
);

double weighted_jaccard_hash_freq(
    const std::unordered_map<std::uint64_t, int>& lft,
    const std::unordered_map<std::uint64_t, int>& rht
);

double compute_token_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
);
double compute_ast_counts_similarity(
    const AstFeatures& left,
    const AstFeatures& right
);

double compute_ast_subtree_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
);

double compute_ast_sequence_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
);

std::vector<std::string> build_ast_grams3(const std::vector<std::string>& preorder_kinds);

double compute_ast_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
);


double compute_ir_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
);

double compute_overall_similarity(
    double token_score,
    double ast_score,
    bool has_ast,
    double ir_score,
    bool has_ir
);