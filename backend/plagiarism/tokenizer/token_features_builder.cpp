#include "token_features_builder.h"

#include <unordered_set>

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
    features.unique_tokens = static_cast<int>(uniq.size());
    return features;
}
