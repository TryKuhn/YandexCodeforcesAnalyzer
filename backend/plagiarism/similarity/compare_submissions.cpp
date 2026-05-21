#include "compare_submissions.h"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <thread>
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
    // ── Stage 1: cheap features in parallel (tokenization + minhash) ─────────
    // Each submission is preprocessed independently, so we can saturate all
    // available cores. Each worker grabs the next unprocessed index atomically.
    // Submissions with empty token code after preprocessing are excluded later
    // (empty features would yield artificial 100% Jaccard similarity via 0/0).
    const std::size_t n_subs = submissions.size();
    std::vector<SubmissionData> prepared(n_subs);
    {
        const unsigned nthreads = std::min(
            static_cast<unsigned>(n_subs),
            std::max(1u, std::thread::hardware_concurrency())
        );
        std::atomic<std::size_t> next{0};
        std::vector<std::thread> workers(nthreads);
        for (auto& w : workers) {
            w = std::thread([&] {
                for (;;) {
                    const std::size_t idx = next.fetch_add(1, std::memory_order_relaxed);
                    if (idx >= n_subs) break;
                    prepared[idx] = BuildSubmissionDataCheap(submissions[idx]);
                }
            });
        }
        for (auto& w : workers) w.join();
    }

    std::unordered_map<std::string, std::size_t> id_to_index;
    id_to_index.reserve(submissions.size());
    for (std::size_t i = 0; i < submissions.size(); ++i) {
        if (!prepared[i].normalized_token_texts.empty()) {
            id_to_index[submissions[i].id] = i;
        }
    }

    // ── Stage 2: LSH candidate generation using minhash ───────────────────────
    const auto candidate_pairs = generate_lsh_candidate_pairs(prepared);

    // ── Stage 3: filter + token-only early exit ────────────────────────────────
    // For each candidate: skip same-participant / cross-problem pairs, then
    // compute token similarity (cheap, features already built) and apply:
    //   • Fast-reject: upper bound < threshold → skip entirely
    //   • Fast-accept: token^1.15 >= threshold → emit result, skip AST
    //   • Gray zone: token alone is ambiguous → defer to AST
    std::vector<std::pair<std::size_t, std::size_t>> valid_candidates;
    std::unordered_set<std::size_t> ast_needed;
    std::vector<SimilarSubmissionPair> result;

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

        // Fast-reject: even perfect AST can't reach threshold
        if (token_upper_bound(token_sim) < threshold) continue;

        // Fast-accept: token similarity alone already meets the threshold.
        // No need to parse AST — saves a full Clang pass for obvious pairs.
        const double token_score = std::pow(token_sim, 1.15);
        if (token_score >= threshold) {
            result.push_back(SimilarSubmissionPair{
                submissions[i].id,
                submissions[j].id,
                token_score * 100.0,
                submissions[i].participant,
                submissions[j].participant,
                submissions[i].problem,
                submissions[j].problem,
                submissions[i].file_name,
                submissions[j].file_name,
                submissions[i].source_path,
                submissions[j].source_path
            });
            continue;
        }

        // Gray zone: token is above reject bound but below accept threshold.
        // Run AST to get a more accurate final score.
        valid_candidates.push_back({i, j});
        ast_needed.insert(i);
        ast_needed.insert(j);
    }

    // ── Stage 4: AST parse only for gray-zone submissions ─────────────────────
    for (const std::size_t idx : ast_needed) {
        EnrichWithAst(prepared[idx]);
    }

    // ── Stage 5: full similarity scoring for gray-zone pairs ──────────────────
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
