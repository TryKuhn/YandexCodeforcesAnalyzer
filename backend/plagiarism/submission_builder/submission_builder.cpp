#include "submission_builder.h"

#include <string>
#include <unordered_set>

#include "normalize_tokens.h"
#include "../preprocessing/normalize.h"
#include "../tokenizer/tokenizer.h"

SubmissionData BuildSubmissionData(const Submission& submission) {
    SubmissionData dat;

    dat.normalizedCode = NormalizeCode(submission.rawCode);

    dat.rawTokens = TokenizerWithClang(dat.normalizedCode);
    dat.normalizedTokens = NormalizeTokens(dat.rawTokens);
    dat.normalizedTokenTexts = TextTokens(dat.normalizedTokens);

    return dat;
}
SubmissionFeatures BuildSubmissionFeatures(const SubmissionData& representation) {
    SubmissionFeatures features;
    std::unordered_set<std::string> unique_tokens;
    for (auto& token : representation.normalizedTokens) {
        if (token.type == TokenType::Literal) {
            features.literals_cnt++;
        } else if (token.type == TokenType::Identifier) {
            features.identifiers_cnt++;
        } else if (token.type == TokenType::Keyword) {
            features.keywords_cnt++;
        } else if (token.type == TokenType::Punctuation) {
            features.punctuations_cnt++;
        }

        unique_tokens.insert(token.text);
        features.tokens_cnt++;
    }
    features.unique_ids = unique_tokens.size();
    return features;
}

