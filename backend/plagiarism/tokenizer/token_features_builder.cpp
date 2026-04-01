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
    for (size_t i = 0; i < normalized_tokens.size() - 2; i++) {
        features.grams3.push_back(
            normalized_tokens[i].text + "|" + normalized_tokens[i + 1].text + "|" + normalized_tokens[i + 2].text
        );
    }
    features.unique_tokens = static_cast<int>(uniq.size());
    return features;
}
