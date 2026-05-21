#include "submission_builder.h"

#include "submission_stages.h"
#include "../similarity/winnowing.h"
#include "../preprocessing/dead_code_stripper.h"

static void fill_token_features(SubmissionData& dat, const Submission& submission) {
    dat.submission_id = submission.id;
    dat.raw_code = submission.rawCode;
    // Both normalization pipelines are currently identical (same g++ -E pass).
    // Compute once to avoid spawning two preprocessor processes per submission.
    dat.ast_code = BuildSubmissionAstCode(submission);
    dat.token_code = dat.ast_code;
    dat.ir_code.clear();
    dat.ir_parse_ok = false;

    dat.tokens = BuildSubmissionTokens(dat.token_code);
    dat.normalized_tokens = BuildNormalizedSubmissionTokens(dat.tokens);
    dat.normalized_token_texts = BuildNormalizedTokenTexts(dat.normalized_tokens);

    auto hashes = build_kgram_hashes(dat.normalized_token_texts, KGRAM);
    auto fingerprints = run_winnowing(hashes, WINNOWING_WINDOW);
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
    // Strip dead code (empty loops, unused locals) only for gray-zone pairs.
    // Runs a full Clang parse, so we defer it until AST disambiguation is needed.
    const std::string clean_code = StripDeadCode(dat.ast_code);
    auto ast_pair = BuildSubmissionAstAndFeatures(clean_code);
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