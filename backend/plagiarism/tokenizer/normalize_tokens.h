#pragma once

#include <string>
#include <vector>

#include "../models/token.h"

/// @brief Normalizes a single token.
///
/// Replaces all numeric and string literal text with canonical placeholders
/// (`NUM` and `STR` respectively). Identifiers and keywords are returned
/// unchanged.
///
/// @param token Raw token from the tokenizer.
/// @return Normalized token with text replaced if it is a literal.
Token NormalizeToken(const Token& token);

/// @brief Normalizes an entire token sequence.
///
/// Applies NormalizeToken to every element.
///
/// @param tokens Raw token sequence.
/// @return Normalized token sequence of the same length.
std::vector<Token> NormalizeTokens(const std::vector<Token>& tokens);

/// @brief Extracts the text field from each token in a sequence.
/// @param tokens Token sequence (raw or normalized).
/// @return Ordered vector of token text strings.
std::vector<std::string> TextTokens(const std::vector<Token>& tokens);