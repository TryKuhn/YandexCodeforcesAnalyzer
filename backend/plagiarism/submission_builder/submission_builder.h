#pragma once

#include "../models/submission.h"
#include "../models/submission_data.h"

/// @brief Builds a fully-featured SubmissionData from a raw submission.
///
/// Runs tokenization, MinHash/winnowing fingerprinting, and full AST analysis.
/// Use this when all similarity features are needed immediately.
///
/// @param submission Raw submission with source code.
/// @return Fully populated SubmissionData.
SubmissionData BuildSubmissionData(const Submission& submission);

/// @brief Builds a SubmissionData with tokenization and MinHash only.
///
/// Skips AST parsing to reduce upfront cost during LSH candidate generation.
/// Call EnrichWithAst() on candidates that require full scoring.
///
/// @param submission Raw submission with source code.
/// @return SubmissionData with token features and MinHash signature populated;
///         AST fields are zero-initialized.
SubmissionData BuildSubmissionDataCheap(const Submission& submission);

/// @brief Adds AST features to a SubmissionData built with BuildSubmissionDataCheap().
///
/// Parses the AST from the already-normalized ast_code field and fills
/// ast_features, ast_subtree_hash_freq, and ast_normalized_sequence in-place.
///
/// @param dat SubmissionData to enrich. Modified in-place.
void EnrichWithAst(SubmissionData& dat);