#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

#include "../models/submission_data.h"

/// @brief Computes set-Jaccard similarity over two token sequences.
///
/// Both sequences are deduplicated before comparison.
/// Returns 0.0 when both sequences are empty.
///
/// @param lft First sequence of token strings.
/// @param rht Second sequence of token strings.
/// @return Jaccard similarity. [0, 1]
double jaccard_score(
    const std::vector<std::string>& lft,
    const std::vector<std::string>& rht
);

/// @brief Computes weighted (multiset) Jaccard similarity over two token sequences.
///
/// Each token's weight is its occurrence count. Returns 0.0 when both sequences
/// are empty.
///
/// @param lft First sequence of token strings.
/// @param rht Second sequence of token strings.
/// @return Weighted Jaccard similarity. [0, 1]
double weighted_jaccard_strings(
    const std::vector<std::string>& lft,
    const std::vector<std::string>& rht
);

/// @brief Computes cosine similarity between two token-frequency vectors.
///
/// Returns 0.0 when either vector has zero norm.
///
/// @param lft Token frequency map for the first submission.
/// @param rht Token frequency map for the second submission.
/// @return Cosine similarity. [0, 1]
double cosine_similarity_score(
    const std::unordered_map<std::string, int>& lft,
    const std::unordered_map<std::string, int>& rht
);

/// @brief Computes weighted Jaccard similarity over hash-frequency maps.
///
/// Used to compare AST subtree hash frequency distributions.
/// Returns 0.0 when both maps are empty.
///
/// @param lft Hash frequency map for the first submission.
/// @param rht Hash frequency map for the second submission.
/// @return Weighted Jaccard similarity. [0, 1]
double weighted_jaccard_hash_freq(
    const std::unordered_map<std::uint64_t, int>& lft,
    const std::unordered_map<std::uint64_t, int>& rht
);

/// @brief Computes combined token similarity (trigrams + cosine).
///
/// Weights: 0.75 × weighted-Jaccard of 3-grams + 0.25 × cosine of token freq.
///
/// @param lft First submission data.
/// @param rht Second submission data.
/// @return Token similarity score. [0, 1]
double compute_token_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
);

/// @brief Computes structural similarity from AST node counts.
///
/// Compares counts of functions, ifs, fors, whiles, returns, and calls.
/// Returns 0.0 when both submissions have all-zero counts.
///
/// @param left AST features for the first submission.
/// @param right AST features for the second submission.
/// @return Count-based AST similarity. [0, 1]
double compute_ast_counts_similarity(
    const AstFeatures& left,
    const AstFeatures& right
);

/// @brief Computes subtree similarity via hash-frequency Jaccard.
///
/// @param lft First submission data.
/// @param rht Second submission data.
/// @return AST subtree similarity. [0, 1]
double compute_ast_subtree_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
);

/// @brief Computes AST sequence similarity using preorder 3-gram Jaccard.
///
/// @param lft First submission data.
/// @param rht Second submission data.
/// @return AST sequence similarity. [0, 1]
double compute_ast_sequence_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
);

/// @brief Builds contiguous 3-grams from a preorder AST node-kind sequence.
///
/// Each gram is three consecutive kind strings joined by `|`.
/// Falls back to the original sequence when fewer than 3 elements.
///
/// @param preorder_kinds Preorder sequence of AST node kind strings.
/// @return Vector of 3-gram strings.
std::vector<std::string> build_ast_grams3(const std::vector<std::string>& preorder_kinds);

/// @brief Computes combined AST similarity (counts + subtrees + sequence).
///
/// Returns 0.0 immediately when either submission's AST failed to parse.
/// Weights: 0.20 × counts + 0.65 × subtree + 0.15 × sequence.
///
/// @param lft First submission data.
/// @param rht Second submission data.
/// @return AST similarity. [0, 1]
double compute_ast_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
);

/// @brief Computes LLVM IR opcode similarity via 3-gram Jaccard.
///
/// Returns 0.0 when either submission's IR is unavailable or failed to parse.
///
/// @param lft First submission data.
/// @param rht Second submission data.
/// @return IR similarity. [0, 1]
double compute_ir_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
);

/// @brief Combines token, AST, and IR scores into a single plagiarism score.
///
/// Applies a mild super-linear curve (power 1.15) to de-emphasize low scores.
/// When AST or IR are unavailable their weight is redistributed to token score.
///
/// @param token_score Token similarity. [0, 1]
/// @param ast_score   AST similarity (ignored when has_ast is false). [0, 1]
/// @param has_ast     Whether AST analysis succeeded for both submissions.
/// @param ir_score    IR similarity (ignored when has_ir is false). [0, 1]
/// @param has_ir      Whether IR analysis succeeded for both submissions.
/// @return Overall plagiarism score. [0, 1]
double compute_overall_similarity(
    double token_score,
    double ast_score,
    bool has_ast,
    double ir_score,
    bool has_ir
);