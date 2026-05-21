#pragma once

#include <unordered_map>
#include <string>
#include <vector>

#include "../ast/ast_features.h"
#include "../ast/ast_hashing.h"
#include "../models/submission.h"
#include "../models/token.h"
#include "../models/token_features.h"

/// @brief Produces the normalized C++ text used for AST parsing.
/// @param submission Raw submission.
/// @return Normalized source text fed to libclang for AST construction.
std::string BuildSubmissionAstCode(const Submission& submission);

/// @brief Produces the normalized C++ text used for tokenization.
/// @param submission Raw submission.
/// @return Normalized source text fed to the tokenizer.
std::string BuildSubmissionTokenCode(const Submission& submission);

/// @brief Compiles normalized C++ source to LLVM IR text.
///
/// Returns an empty string and sets the ir_parse_ok flag to false when
/// compilation is unavailable or fails.
///
/// @param normalized_code Preprocessed C++ source text.
/// @return LLVM IR text, or empty string on failure.
std::string BuildSubmissionIrCode(const std::string& normalized_code);

/// @brief Tokenizes normalized C++ source via libclang.
/// @param token_code Normalized C++ source text.
/// @return Raw token sequence with offsets.
std::vector<Token> BuildSubmissionTokens(const std::string& token_code);

/// @brief Normalizes a raw token sequence (collapse literals, unify identifiers).
/// @param tokens Raw token sequence from BuildSubmissionTokens().
/// @return Normalized token sequence.
std::vector<Token> BuildNormalizedSubmissionTokens(const std::vector<Token>& tokens);

/// @brief Extracts text strings from a normalized token sequence.
/// @param normalized_tokens Normalized token sequence.
/// @return Ordered vector of token text strings.
std::vector<std::string> BuildNormalizedTokenTexts(
    const std::vector<Token>& normalized_tokens
);

/// @brief Builds token frequency and n-gram features from raw and normalized tokens.
/// @param raw_tokens        Raw token sequence.
/// @param normalized_tokens Normalized token sequence.
/// @return Populated TokenFeatures struct.
TokenFeatures BuildSubmissionTokenFeatures(
    const std::vector<Token>& raw_tokens,
    const std::vector<Token>& normalized_tokens
);

/// @brief Parses AST features (counts) from normalized C++ source.
/// @param ast_code Normalized C++ source text.
/// @return AstFeatures with parse_ok set according to libclang result.
AstFeatures BuildSubmissionAstFeatures(const std::string& ast_code);

/// @brief Builds the full AST tree from normalized C++ source.
/// @param ast_code Normalized C++ source text.
/// @return AstTree with parse_ok set according to libclang result.
AstTree BuildSubmissionAstTree(const std::string& ast_code);

/// @brief Builds both AST features and tree in a single libclang parse.
///
/// More efficient than calling BuildSubmissionAstFeatures and
/// BuildSubmissionAstTree separately.
///
/// @param ast_code Normalized C++ source text.
/// @return Pair of (AstFeatures, AstTree).
std::pair<AstFeatures, AstTree> BuildSubmissionAstAndFeatures(const std::string& ast_code);

/// @brief Builds a subtree hash frequency map from an AST.
///
/// Subtrees smaller than min_subtree_size nodes are excluded to reduce noise.
///
/// @param tree             Parsed AST tree.
/// @param min_subtree_size Minimum subtree node count to include. Default 2.
/// @return Map of subtree hash → occurrence count.
std::unordered_map<std::uint64_t, int> BuildSubmissionAstSubtreeHashFreq(
    const AstTree& tree,
    int min_subtree_size = 2
);

/// @brief Builds a preorder node-kind sequence from an AST for sequence comparison.
/// @param tree Parsed AST tree.
/// @return Ordered vector of normalized AST node kind strings.
std::vector<std::string> BuildSubmissionAstNormalizedSequence(const AstTree& tree);

