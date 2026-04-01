#include <unordered_set>

#include "normalize_tokens.h"

const std::unordered_set<std::string> allowed_ids = {
    "std",
    "vector",
    "string",
    "map",
    "set",
    "unordered_map",
    "unordered_set",
    "queue",
    "stack",
    "deque",
    "pair",
    "tuple",
    "sort",
    "lower_bound",
    "upper_bound",
    "push_back",
    "emplace_back",
    "begin",
    "end",
    "cin",
    "cout",
    "endl",
    "min",
    "max",
    "swap",
    "abs"
};

bool IsString(const std::string& str) {
    return (!str.empty() && str[0] == '"');
}

bool IsChar(const std::string& str) {
    return (!str.empty() && str[0] == '\'');
}

Token NormalizeToken(const Token& token) {
    Token returned_token = token;

    if (token.type == TokenType::Identifier) {
        if (allowed_ids.find(token.text) == allowed_ids.end()) {
            returned_token.text = "ID";
        }

    } else if (token.type == TokenType::Literal) {
        if (IsString(token.text)) {
            returned_token.text = "STR";
        } else if (IsChar(token.text)) {
            returned_token.text = "CHAR";
        } else {
            returned_token.text = "NUM";
        }
    }
    return returned_token;
}
std::vector<Token> NormalizeTokens(const std::vector<Token>& tokens) {
    std::vector<Token> return_tokens;
    return_tokens.reserve(tokens.size());

    for (const auto& token : tokens) {
        return_tokens.push_back(NormalizeToken(token));
    }
    return return_tokens;
}

std::vector<std::string> TextTokens(const std::vector<Token>& tokens) {
    std::vector < std::string > return_texts;
    return_texts.reserve(tokens.size());
    for (const auto& token : tokens) {
        return_texts.push_back(token.text);
    }
    return return_texts;
}