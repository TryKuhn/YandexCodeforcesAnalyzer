#include <unordered_set>

#include "normalize_tokens.h"

// Identifiers preserved verbatim after normalization.
// Two groups: (1) container/algorithm names that reflect structural choices;
// (2) member names that distinguish operations (e.g. push_back vs insert).
// User-defined names and anything not in this list collapse to "ID".
// "std" is intentionally absent — StripNamespaceQualifiers removes it upstream.
const std::unordered_set<std::string> allowed_ids = {
    // Containers
    "vector", "string", "map", "set", "unordered_map", "unordered_set",
    "multimap", "multiset", "queue", "priority_queue", "stack", "deque",
    "list", "array", "bitset", "pair", "tuple",

    // Algorithms
    "sort", "stable_sort", "nth_element",
    "lower_bound", "upper_bound", "binary_search",
    "min", "max", "min_element", "max_element",
    "fill", "copy", "reverse", "rotate", "unique",
    "accumulate", "count", "count_if",
    "find", "find_if",
    "next_permutation", "prev_permutation",
    "gcd", "lcm", "abs", "swap",

    // Container members
    "push_back", "pop_back", "emplace_back",
    "push", "pop", "top", "front", "back",
    "insert", "emplace", "erase", "clear",
    "begin", "end", "rbegin", "rend",
    "size", "empty", "resize", "reserve", "capacity",
    "at", "contains", "count",

    // Pair/tuple members
    "first", "second", "make_pair", "make_tuple", "get",

    // I/O
    "cin", "cout", "cerr", "endl", "printf", "scanf",
    "getline", "puts", "gets",

    // String / conversion
    "to_string", "stoi", "stol", "stoll", "stof", "stod",
    "strlen", "strcmp", "strcpy",

    // Memory
    "make_shared", "make_unique",
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