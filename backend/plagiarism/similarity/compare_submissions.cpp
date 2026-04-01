#include "compare_submissions.h"

#include "metrics.h"
#include "../submission_builder/submission_builder.h"

double compute_similarity(const Submission& frst, const Submission& scnd) {
    SubmissionData lft = BuildSubmissionData(frst);
    SubmissionData rht = BuildSubmissionData(scnd);

    double token_similarity = compute_token_similarity(lft, rht);
    double ast_similarity = compute_ast_similarity(lft, rht);

    bool has_ast = lft.ast_features.parse_ok && rht.ast_features.parse_ok;

    return compute_overall_similarity(token_similarity, ast_similarity, has_ast);
}