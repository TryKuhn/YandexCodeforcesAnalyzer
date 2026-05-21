#pragma once

#include <vector>

#include "../models/submission.h"
#include "../models/similar_submission_pair.h"

/// @brief Computes pairwise plagiarism similarity for a set of submissions.
///
/// Uses LSH candidate generation to avoid O(n²) full comparisons, then scores
/// each candidate pair with token and AST similarity metrics.
///
/// @param submissions Collection of submissions to compare.
/// @param threshold   Minimum overall score for a pair to be included. [0, 1]
/// @return Pairs whose overall similarity meets or exceeds threshold,
///         sorted by descending plagiarism_percent.
std::vector<SimilarSubmissionPair> compute_similarity_pairs(
    const std::vector<Submission>& submissions,
    double threshold = 0.0
);
