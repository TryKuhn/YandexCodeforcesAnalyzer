#pragma once

#include <string>
#include <vector>
#include "../models/token.h"

/// @brief Tokenizes C++ source code using libclang.
///
/// Creates an in-memory translation unit and extracts every token together
/// with its type (Punctuation, Keyword, Identifier, Literal) and byte offset.
/// Returns an empty vector when libclang fails to parse the input.
///
/// @param code Normalized C++ source text.
/// @return Ordered sequence of tokens with type and offset.
std::vector<Token> TokenizerWithClang(const std::string& code);