#pragma once

#include <string>

/// @brief Prepares C++ source for tokenization.
///
/// Pipeline: normalize line endings → remove comments → expand aliases →
/// strip directives and empty lines → collapse whitespace.
///
/// @param code Raw C++ source code.
/// @return Normalized source text suitable for libclang tokenization.
std::string NormalizeForTokenizer(const std::string& code);

/// @brief Prepares C++ source for AST parsing.
///
/// Applies the same pipeline as NormalizeForTokenizer. A separate entry
/// point is kept so callers can diverge the two pipelines later without
/// breaking the API.
///
/// @param code Raw C++ source code.
/// @return Normalized source text suitable for libclang AST analysis.
std::string NormalizeForAST(const std::string& code);