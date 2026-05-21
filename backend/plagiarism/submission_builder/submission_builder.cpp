#include "submission_builder.h"

#include "submission_stages.h"
#include "../similarity/winnowing.h"

static void fill_token_features(SubmissionData& dat, const Submission& submission) {
    dat.submission_id = submission.id;
    dat.raw_code = submission.rawCode;
    dat.ast_code = BuildSubmissionAstCode(submission);
    dat.token_code = BuildSubmissionTokenCode(submission);
    dat.ir_code.clear();
    dat.ir_parse_ok = false;

    dat.tokens = BuildSubmissionTokens(dat.token_code);
    dat.normalized_tokens = BuildNormalizedSubmissionTokens(dat.tokens);
    dat.normalized_token_texts = BuildNormalizedTokenTexts(dat.normalized_tokens);

    auto hashes = build_kgram_hashes(dat.normalized_token_texts, KGRAM);
    auto fingerprints = run_winnowing(hashes, 5);
    dat.winnowing_features.fingerprints = fingerprints;
    dat.winnowing_features.minhash_signature = build_minhash_signature(fingerprints);

    dat.token_features = BuildSubmissionTokenFeatures(dat.tokens, dat.normalized_tokens);
}

SubmissionData BuildSubmissionDataCheap(const Submission& submission) {
    SubmissionData dat;
    fill_token_features(dat, submission);
    return dat;
}

void EnrichWithAst(SubmissionData& dat) {
    auto ast_pair = BuildSubmissionAstAndFeatures(dat.ast_code);
    dat.ast_features = std::move(ast_pair.first);
    const AstTree ast_tree = std::move(ast_pair.second);
    dat.ast_subtree_hash_freq = BuildSubmissionAstSubtreeHashFreq(ast_tree);
    dat.ast_normalized_sequence = BuildSubmissionAstNormalizedSequence(ast_tree);
}

SubmissionData BuildSubmissionData(const Submission& submission) {
    SubmissionData dat;
    fill_token_features(dat, submission);
    EnrichWithAst(dat);
    return dat;
}