#include "token_features_builder.h"

#include <unordered_set>

static bool IsParenPunctuation(const Token& token) {
    return token.type == TokenType::Punctuation && (token.text == "(" || token.text == ")");
}

TokenFeatures BuildTokenFeatures(const std::vector<Token>& raw_tokens,
                                 const std::vector<Token>& normalized_tokens) {
    TokenFeatures features;

    for (const auto& token : normalized_tokens) {
        features.tokens_cnt++;
        if (token.type == TokenType::Identifier) {
            features.identifiers_cnt++;
        } else if (token.type == TokenType::Literal) {
            features.literals_cnt++;
        } else if (token.type == TokenType::Punctuation) {
            features.punctuations_cnt++;
        } else if (token.type == TokenType::Keyword) {
            features.keywords_cnt++;
        }
        features.freq[token.text]++;
    }

    std::unordered_set<std::string> uniq;
    for (const auto& token : raw_tokens) {
        uniq.insert(token.text);
    }

    std::vector<std::string> grams_source;
    grams_source.reserve(normalized_tokens.size());
    for (const auto& token : normalized_tokens) {
        if (IsParenPunctuation(token)) {
            continue;
        }
        grams_source.push_back(token.text);
    }

    for (size_t i = 0; i + 2 < grams_source.size(); i++) {
        features.grams3.push_back(
            grams_source[i] + "|" + grams_source[i + 1] + "|" + grams_source[i + 2]
        );
    }

    features.unique_tokens = static_cast<int>(uniq.size());
    return features;
}
