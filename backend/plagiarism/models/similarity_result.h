#pragma once

/// @brief Decomposed similarity scores returned by the full scoring pipeline.
struct SimilarityResult {
    double token_score = 0.0;
    double ast_score = 0.0;
    double overall_score = 0.0;
};
