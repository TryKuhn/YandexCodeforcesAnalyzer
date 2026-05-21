#pragma once

#include <cstddef>
#include <string>

/// @brief Coarse token classification produced by the libclang tokenizer.
enum class TokenType {
    Punctuation,
    Keyword,
    Identifier,
    Literal,
    Unknown
};

/// @brief A single token extracted from C++ source code.
struct Token {
    TokenType type;
    std::string text;
    std::size_t offset;
};