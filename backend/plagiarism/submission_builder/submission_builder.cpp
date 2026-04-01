#include "submission_builder.h"

#include "../preprocessing/normalize.h"
#include "../tokenizer/tokenizer.h"
#include "../tokenizer/normalize_tokens.h"
#include "../tokenizer/token_features_builder.h"
#include "../ast/ast_analyzer.h"

SubmissionData BuildSubmissionData(const Submission& submission) {
    SubmissionData dat;

    dat.raw_code = submission.rawCode;
    dat.ast_code = NormalizeForAST(dat.raw_code);
    dat.token_code = NormalizeForTokenizer(dat.raw_code);

    dat.tokens = TokenizerWithClang(dat.token_code);
    dat.normalized_tokens = NormalizeTokens(dat.tokens);
    dat.normalized_token_texts = TextTokens(dat.normalized_tokens);

    dat.token_features = BuildTokenFeatures(dat.tokens, dat.normalized_tokens);
    dat.ast_features = analyze_ast(dat.ast_code);

    return dat;
}