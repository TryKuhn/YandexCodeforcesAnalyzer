#include "metrics.h"

#include <unordered_set>
#include <cmath>

double jaccard_score(
    const std::vector<std::string>& lft,
    const std::vector<std::string>& rht
) {
    std::unordered_set<std::string> lft_set(lft.begin(), lft.end());
    std::unordered_set<std::string> rht_set(rht.begin(), rht.end());

    if (lft_set.empty() && rht_set.empty()) {
        return 1.0;
    }

    int intersec = 0;
    for (const auto& token : lft_set) {
        if (rht_set.find(token) != rht_set.end()) {
            ++intersec;
        }
    }

    std::size_t union_size = lft_set.size();
    for (const auto& token : rht_set) {
        if (lft_set.find(token) == lft_set.end()) {
            ++union_size;
        }
    }

    return static_cast<double>(intersec) / static_cast<double>(union_size);

}

double cosine_similarity_score(
    const std::unordered_map<std::string, int>& lft,
    const std::unordered_map<std::string, int>& rht
) {
    double lft_norm = 0, rht_norm = 0;
    double scalar = 0.0;

    for (const auto& to : lft) {
        lft_norm += static_cast<double>(to.second) * static_cast<double>(to.second);

        auto it = rht.find(to.first);
        if (it != rht.end()) {
            scalar += static_cast<double>(to.second) * static_cast<double>(it->second);
        }
    }
    for (const auto& to : rht) {
        rht_norm += static_cast<double>(to.second) * static_cast<double>(to.second);
    }
    if (lft_norm == 0.0 && rht_norm == 0.0) {
        return 1.0;
    }
    if (lft_norm == 0.0 || rht_norm == 0.0 ) {
        return 0.0;
    }
    return scalar / (std::sqrt(lft_norm) * std::sqrt(rht_norm));
}

double compute_token_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
) {
    double grams3 = jaccard_score(lft.token_features.grams3, rht.token_features.grams3);

    double freq_cos = cosine_similarity_score(lft.token_features.freq,rht.token_features.freq);

    return 0.7 * grams3 + 0.3 * freq_cos;
    // PRELIMINARY formula for features contrubition
}
double compute_ast_counts_similarity(
    const AstFeatures& left,
    const AstFeatures& right
) {
    int diff_sum = 0;
    int max_sum = 0;

    diff_sum += std::abs(left.functions_cnt - right.functions_cnt);
    diff_sum += std::abs(left.ifs_cnt - right.ifs_cnt);
    diff_sum += std::abs(left.fors_cnt - right.fors_cnt);
    diff_sum += std::abs(left.whiles_cnt - right.whiles_cnt);
    diff_sum += std::abs(left.returns_cnt - right.returns_cnt);
    diff_sum += std::abs(left.calls_cnt - right.calls_cnt);

    max_sum += std::max(left.functions_cnt, right.functions_cnt);
    max_sum += std::max(left.ifs_cnt, right.ifs_cnt);
    max_sum += std::max(left.fors_cnt, right.fors_cnt);
    max_sum += std::max(left.whiles_cnt, right.whiles_cnt);
    max_sum += std::max(left.returns_cnt, right.returns_cnt);
    max_sum += std::max(left.calls_cnt, right.calls_cnt);

    if (max_sum == 0) {
        return 1.0;
    }

    return 1.0 - static_cast<double>(diff_sum) / static_cast<double>(max_sum);
}

std::vector<std::string> build_ast_grams3(const std::vector<std::string>& preorder_kinds) {
    std::vector<std::string> grams3;

    for (size_t i = 0; i + 2 < preorder_kinds.size(); ++i) {
        grams3.push_back(preorder_kinds[i] + "|" + preorder_kinds[i + 1] + "|" + preorder_kinds[i + 2]);
    }

    return grams3;
}
double compute_ast_similarity(const SubmissionData& lft, const SubmissionData& rht) {
    if (!lft.ast_features.parse_ok || !rht.ast_features.parse_ok) {
        return 0.0;
    }
    double count_score = compute_ast_counts_similarity(lft.ast_features, rht.ast_features);

    std::vector < std::string > lft_grams = build_ast_grams3(lft.ast_features.preorder_kinds);
    std::vector < std::string > rht_grams = build_ast_grams3(rht.ast_features.preorder_kinds);

    double grams3 = jaccard_score(lft_grams, rht_grams);
    return 0.6 * count_score + 0.4 * grams3;
    //PRELIMINARY formula

}

double compute_overall_similarity(double token_score, double ast_score, bool has_ast) {
    if (!has_ast) {
        return token_score;
    }
    return 0.7 * token_score + 0.3 * ast_score;
    //PRELIMINARY 
}