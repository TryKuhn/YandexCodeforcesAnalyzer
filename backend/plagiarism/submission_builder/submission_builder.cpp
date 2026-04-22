#include "submission_builder.h"

#include "submission_stages.h"
#include "../similarity/winnowing.h"

SubmissionData BuildSubmissionData(const Submission& submission) {
    SubmissionData dat;

    dat.submission_id = submission.id;
    dat.raw_code = submission.rawCode;
    dat.ast_code = BuildSubmissionAstCode(submission);
    dat.token_code = BuildSubmissionTokenCode(submission);
    dat.ir_code = BuildSubmissionIrCode(dat.ast_code);
    dat.ir_parse_ok = !dat.ir_code.empty();

    dat.tokens = BuildSubmissionTokens(dat.token_code);
    dat.normalized_tokens = BuildNormalizedSubmissionTokens(dat.tokens);
    dat.normalized_token_texts = BuildNormalizedTokenTexts(dat.normalized_tokens);

    auto hashes = build_kgram_hashes(dat.normalized_token_texts, KGRAM);
    auto fingerprints = run_winnowing(hashes, 5);
    dat.winnowing_features.fingerprints = fingerprints;
    dat.winnowing_features.minhash_signature = build_minhash_signature(fingerprints);

    dat.token_features = BuildSubmissionTokenFeatures(dat.tokens, dat.normalized_tokens);
    dat.ast_features = BuildSubmissionAstFeatures(dat.ast_code);

    const AstTree ast_tree = BuildSubmissionAstTree(dat.ast_code);
    dat.ast_subtree_hash_freq = BuildSubmissionAstSubtreeHashFreq(ast_tree);
    dat.ast_normalized_sequence = BuildSubmissionAstNormalizedSequence(ast_tree);

    return dat;
}