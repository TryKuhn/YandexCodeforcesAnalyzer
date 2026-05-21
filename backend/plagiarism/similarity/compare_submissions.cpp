#include "compare_submissions.h"

#include <algorithm>
#include <cmath>
#include <unordered_map>
#include <unordered_set>

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

// Upper bound on the final score given only token similarity.
// Assumes perfect AST (score=1.0) and no IR (disabled), which is the most
// optimistic scenario. If even this can't reach the threshold, the pair is skipped.
static double token_upper_bound(double token_sim) {
    // has_ast=true, has_ir=false → linear = 0.65*tok + 0.35*1.0
    return std::pow(0.65 * token_sim + 0.35, 1.15);
}


std::vector<SimilarSubmissionPair> compute_similarity_pairs(
    const std::vector<Submission>& submissions,
    double threshold
) {
    // ── Stage 1: cheap features (tokenization + minhash) for all submissions ──
    // AST parsing is deferred until we know which submissions survive filtering.
    std::vector<SubmissionData> prepared;
    prepared.reserve(submissions.size());
    for (const auto& sub : submissions) {
        prepared.push_back(BuildSubmissionDataCheap(sub));
    }

    std::unordered_map<std::string, std::size_t> id_to_index;
    id_to_index.reserve(submissions.size());
    for (std::size_t i = 0; i < submissions.size(); ++i) {
        id_to_index[submissions[i].id] = i;
    }

    // ── Stage 2: LSH candidate generation using minhash ───────────────────────
    const auto candidate_pairs = generate_lsh_candidate_pairs(prepared);

    // ── Stage 3: filter + token-only early exit ────────────────────────────────
    // For each candidate: skip same-participant / cross-problem pairs, then
    // compute token similarity (cheap, features already built) and apply an
    // optimistic upper-bound check to discard obvious non-matches before
    // paying the cost of Clang AST parsing.
    std::vector<std::pair<std::size_t, std::size_t>> valid_candidates;
    std::unordered_set<std::size_t> ast_needed;

    for (const auto& [left_id, right_id] : candidate_pairs) {
        const auto left_it = id_to_index.find(left_id);
        const auto right_it = id_to_index.find(right_id);
        if (left_it == id_to_index.end() || right_it == id_to_index.end()) continue;

        const std::size_t i = left_it->second;
        const std::size_t j = right_it->second;

        if (submissions[i].participant == submissions[j].participant) continue;
        if (!submissions[i].problem.empty() &&
            !submissions[j].problem.empty() &&
            submissions[i].problem != submissions[j].problem) continue;

        const double token_sim = compute_token_similarity(prepared[i], prepared[j]);
        if (token_upper_bound(token_sim) < threshold) continue;

        valid_candidates.push_back({i, j});
        ast_needed.insert(i);
        ast_needed.insert(j);
    }

    // ── Stage 4: AST parse only for submissions in surviving pairs ─────────────
    for (const std::size_t idx : ast_needed) {
        EnrichWithAst(prepared[idx]);
    }

    // ── Stage 5: full similarity scoring ──────────────────────────────────────
    std::vector<SimilarSubmissionPair> result;
    for (const auto& [i, j] : valid_candidates) {
        const double similarity = compute_similarity_impl(prepared[i], prepared[j]);
        if (similarity < threshold) continue;

        result.push_back(SimilarSubmissionPair{
            submissions[i].id,
            submissions[j].id,
            similarity * 100.0,

            submissions[i].participant,
            submissions[j].participant,

            submissions[i].problem,
            submissions[j].problem,

            submissions[i].file_name,
            submissions[j].file_name,

            submissions[i].source_path,
            submissions[j].source_path
        });
    }

    std::sort(result.begin(), result.end(), [](const SimilarSubmissionPair& l, const SimilarSubmissionPair& r) {
        if (l.plagiarism_percent != r.plagiarism_percent) return l.plagiarism_percent > r.plagiarism_percent;
        if (l.first_submission_id != r.first_submission_id) return l.first_submission_id < r.first_submission_id;
        return l.second_submission_id < r.second_submission_id;
    });

    return result;
}
