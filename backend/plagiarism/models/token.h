#pragma once

#include <cstddef>
#include <string>

enum class TokenType {
    Punctuation,
    Keyword,
    Identifier,
    Literal,
    Unknown
};

struct Token {
    TokenType type;
    std::string text;
    std::size_t offset;
};