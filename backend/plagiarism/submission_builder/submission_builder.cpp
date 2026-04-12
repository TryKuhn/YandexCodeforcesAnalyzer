#include "submission_builder.h"

#include "submission_stages.h"
#include "../similarity/winnowing.h"

SubmissionData BuildSubmissionData(const Submission& submission) {
    SubmissionData dat;

    dat.submission_id = submission.id;
    dat.raw_code = submission.rawCode;
    dat.ast_code = BuildSubmissionAstCode(submission);
    dat.token_code = BuildSubmissionTokenCode(submission);

    dat.tokens = BuildSubmissionTokens(dat.token_code);
    dat.normalized_tokens = BuildNormalizedSubmissionTokens(dat.tokens);
    dat.normalized_token_texts = BuildNormalizedTokenTexts(dat.normalized_tokens);

    auto hashes = build_kgram_hashes(dat.normalized_token_texts, KGRAM);
    auto fingerprints = run_winnowing(hashes, 5);
    dat.winnowing_features.fingerprints = fingerprints;
    dat.winnowing_features.minhash_signature = build_minhash_signature(fingerprints);

    dat.token_features = BuildSubmissionTokenFeatures(dat.tokens, dat.normalized_tokens);
    dat.ast_features = BuildSubmissionAstFeatures(dat.ast_code);

    return dat;
}