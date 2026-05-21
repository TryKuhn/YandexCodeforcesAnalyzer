#include "metrics.h"

#include <unordered_set>
#include <cmath>
#include <sstream>

static std::vector<std::string> extract_ir_opcodes(const std::string& ir_code) {
    std::vector<std::string> ops;
    std::istringstream in(ir_code);
    std::string line;

    while (std::getline(in, line)) {
        std::size_t first = line.find_first_not_of(" \t");
        if (first == std::string::npos) {
            continue;
        }

        char lead = line[first];
        if (lead == ';' || lead == '!' || lead == '}') {
            continue;
        }

        if (line.compare(first, 6, "define") == 0 ||
            line.compare(first, 7, "declare") == 0 ||
            line.compare(first, 5, "entry") == 0) {
            continue;
        }

        std::size_t pos = first;
        if (line[pos] == '%') {
            std::size_t eq = line.find('=', pos);
            if (eq == std::string::npos) {
                continue;
            }
            pos = line.find_first_not_of(" \t", eq + 1);
            if (pos == std::string::npos) {
                continue;
            }
        }

        std::size_t end = line.find_first_of(" \t(,", pos);
        if (end == std::string::npos) {
            end = line.size();
        }

        std::string op = line.substr(pos, end - pos);
        if (!op.empty() && op != "label") {
            ops.push_back(op);
        }
    }

    return ops;
}


double jaccard_score(
    const std::vector<std::string>& lft,
    const std::vector<std::string>& rht
) {
    std::unordered_set<std::string> lft_set(lft.begin(), lft.end());
    std::unordered_set<std::string> rht_set(rht.begin(), rht.end());

    if (lft_set.empty() && rht_set.empty()) {
        return 0.0;
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
        return 0.0;
    }
    if (lft_norm == 0.0 || rht_norm == 0.0 ) {
        return 0.0;
    }
    return scalar / (std::sqrt(lft_norm) * std::sqrt(rht_norm));
}

double weighted_jaccard_strings(
    const std::vector<std::string>& lft,
    const std::vector<std::string>& rht
) {
    std::unordered_map<std::string, int> lft_freq, rht_freq;
    for (const auto& s : lft) lft_freq[s]++;
    for (const auto& s : rht) rht_freq[s]++;

    double intersec = 0.0, each = 0.0;
    for (const auto& [k, v] : lft_freq) {
        auto it = rht_freq.find(k);
        if (it != rht_freq.end()) {
            intersec += std::min(v, it->second);
            each += std::max(v, it->second);
        } else {
            each += v;
        }
    }
    for (const auto& [k, v] : rht_freq) {
        if (lft_freq.find(k) == lft_freq.end()) {
            each += v;
        }
    }
    if (each == 0.0) return 0.0;
    return intersec / each;
}

double compute_token_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
) {
    double grams3 = weighted_jaccard_strings(lft.token_features.grams3, rht.token_features.grams3);
    double freq_cos = cosine_similarity_score(lft.token_features.freq, rht.token_features.freq);
    return 0.75 * grams3 + 0.25 * freq_cos;
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
        return 0.0;
    }

    return 1.0 - static_cast<double>(diff_sum) / static_cast<double>(max_sum);
}
double weighted_jaccard_hash_freq(
    const std::unordered_map<std::uint64_t, int>& lft,
    const std::unordered_map<std::uint64_t, int>& rht
) {
    if (lft.empty() && rht.empty()) {
        return 0.0;
    }

    double intersec = 0.0;
    double each = 0.0;

    for (const auto& to : lft) {
        auto it = rht.find(to.first);
        if (it != rht.end()) {
            intersec += std::min(static_cast<double>(to.second), static_cast<double>(it->second));
            each += std::max(static_cast<double>(to.second), static_cast<double>(it->second));
        } else {
            each += static_cast<double>(to.second);
        }
    }
    for (const auto& to : rht) {
        if (lft.find(to.first) == lft.end()) {
            each += static_cast<double>(to.second);
        }
    }
    if (each == 0.0) {
        return 0.0;
    }
    return intersec / each;
}
double compute_ast_subtree_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
) {
    return weighted_jaccard_hash_freq(lft.ast_subtree_hash_freq, rht.ast_subtree_hash_freq);
}

double compute_ast_sequence_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
) {
    std::vector<std::string> lft_grams = build_ast_grams3(lft.ast_normalized_sequence);
    std::vector<std::string> rht_grams = build_ast_grams3(rht.ast_normalized_sequence);


    return jaccard_score(lft_grams, rht_grams);
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

    const double count_score = compute_ast_counts_similarity(lft.ast_features, rht.ast_features);
    const double subtree_score = compute_ast_subtree_similarity(lft, rht);
    const double sequence_score = compute_ast_sequence_similarity(lft, rht);
    return 0.20 * count_score + 0.65 * subtree_score + 0.15 * sequence_score;
}

double compute_ir_similarity(
    const SubmissionData& lft,
    const SubmissionData& rht
) {
    if (!lft.ir_parse_ok || !rht.ir_parse_ok) {
        return 0.0;
    }

    std::vector<std::string> lft_ops = extract_ir_opcodes(lft.ir_code);
    std::vector<std::string> rht_ops = extract_ir_opcodes(rht.ir_code);

    std::vector<std::string> lft_grams = build_ast_grams3(lft_ops);
    std::vector<std::string> rht_grams = build_ast_grams3(rht_ops);
    return jaccard_score(lft_grams, rht_grams);
}

double compute_overall_similarity(
    double token_score,
    double ast_score,
    bool has_ast,
    double ir_score,
    bool has_ir
) {
    if (!has_ast && !has_ir) {
        return std::pow(token_score, 1.15);
    }

    if (has_ast && !has_ir) {
        const double linear = 0.65 * token_score + 0.35 * ast_score;
        return std::pow(linear, 1.15);
    }

    if (!has_ast && has_ir) {
        const double linear = 0.85 * token_score + 0.15 * ir_score;
        return std::pow(linear, 1.15);
    }

    const double linear = 0.58 * token_score + 0.30 * ast_score + 0.12 * ir_score;
    return std::pow(linear, 1.15);
}