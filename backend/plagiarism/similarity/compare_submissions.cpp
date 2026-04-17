#include "compare_submissions.h"

#include <algorithm>
#include <unordered_map>

#include "lsh.h"
#include "metrics.h"
#include "../submission_builder/submission_builder.h"

static double compute_similarity_impl(const SubmissionData& lft, const SubmissionData& rht) {
    double token_similarity = compute_token_similarity(lft, rht);
    double ast_similarity = compute_ast_similarity(lft, rht);
    double ir_similarity = compute_ir_similarity(lft, rht);

    bool has_ast = lft.ast_features.parse_ok && rht.ast_features.parse_ok;
    bool has_ir = lft.ir_parse_ok && rht.ir_parse_ok;

    return compute_overall_similarity(token_similarity, ast_similarity, has_ast, ir_similarity, has_ir);
}


std::vector<SimilarSubmissionPair> compute_similarity_pairs(
    const std::vector<Submission>& submissions,
    double threshold
) {
    std::vector<SubmissionData> prepared;
    prepared.reserve(submissions.size());

    for (const auto& submission : submissions) {
        prepared.push_back(BuildSubmissionData(submission));
    }

    std::vector<SimilarSubmissionPair> result;

    std::unordered_map<int, std::size_t> id_to_index;
    id_to_index.reserve(submissions.size());
    for (std::size_t i = 0; i < submissions.size(); ++i) {
        id_to_index[submissions[i].id] = i;
    }

    const auto candidate_pairs = generate_lsh_candidate_pairs(prepared);
    for (const auto& [left_id, right_id] : candidate_pairs) {
        const auto left_it = id_to_index.find(left_id);
        const auto right_it = id_to_index.find(right_id);
        if (left_it == id_to_index.end() || right_it == id_to_index.end()) {
            continue;
        }

        const std::size_t i = left_it->second;
        const std::size_t j = right_it->second;

        double similarity = compute_similarity_impl(prepared[i], prepared[j]);
        if (similarity < threshold) {
            continue;
        }

        result.push_back(SimilarSubmissionPair{
            submissions[i].id,
            submissions[j].id,
            similarity * 100.0
        });
    }

    std::sort(result.begin(), result.end(), [](const SimilarSubmissionPair& left, const SimilarSubmissionPair& right) {
        if (left.plagiarism_percent != right.plagiarism_percent) {
            return left.plagiarism_percent > right.plagiarism_percent;
        }

        if (left.first_submission_id != right.first_submission_id) {
            return left.first_submission_id < right.first_submission_id;
        }

        return left.second_submission_id < right.second_submission_id;
    });

    return result;
}
