#pragma once

#include <vector>

#include "../models/token.h"
#include "../models/token_features.h"

/// @brief Builds token feature statistics from raw and normalized token sequences.
///
/// Computes per-type counts (keywords, identifiers, literals, punctuation),
/// a token frequency map, and a 3-gram sequence from the normalized token texts.
///
/// @param raw_tokens        Raw (un-normalized) token sequence for count stats.
/// @param normalized_tokens Normalized token sequence for frequency and n-gram features.
/// @return Populated TokenFeatures struct.
TokenFeatures BuildTokenFeatures(const std::vector<Token>& raw_tokens,
    const std::vector<Token>& normalized_tokens);