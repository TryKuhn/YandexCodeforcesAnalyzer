#include "lsh.h"
#include <boost/functional/hash.hpp>
#include <cstdint>
#include <utility>
#include <unordered_map>

std::uint64_t build_lsh_bucket_key(
    const std::vector<std::uint64_t>& signature,
    std::size_t start,
    int rows_per_band
) {
    std::uint64_t ret = 0;

    for (size_t i = 0; i < rows_per_band; i++) {
        ret = splitmix64(ret ^ signature[start + i]);
    }
    return ret;
}

struct PairHash {
    std::size_t operator()(const std::pair<int, int>& p) const noexcept {
        std::size_t seed = 0;
        boost::hash_combine(seed, p.first);
        boost::hash_combine(seed, p.second);
        return seed;
    }
};
std::vector<std::pair < int, int > > generate_lsh_candidate_pairs(
    const std::vector<SubmissionData>& prepared
) {
    std::vector < std:: pair < int, int > > candidates;

    std::unordered_map<std::uint64_t, std::vector<int>> buckets;
    std::unordered_map<std::pair < int, int >, int, PairHash > in_one_bucket_cnt;
    for (auto& to : prepared) {
        for (size_t band = 0; band < BANDS; band++) {
            std::uint64_t bucket_key = build_lsh_bucket_key(
                to.winnowing_features.minhash_signature,
                band * ROWS_PER_BAND
            );
            buckets[bucket_key].push_back(to.submission_id);
        }
    }

    for (auto& [hashh, indexes] : buckets) {
        if (indexes.size() > MAX_BUCKET_SIZE) {
            continue;
        }
        for (size_t i = 0; i < indexes.size(); i++) {
            for (size_t j = i + 1; j < indexes.size(); j++) {
                std::pair < int, int > p = {std::min(indexes[i], indexes[j]), std::max(indexes[i], indexes[j])};
                in_one_bucket_cnt[p]++;
            }
        }
    }

    for (auto& [p, cnt] : in_one_bucket_cnt) {
        if (cnt >= MIN_COMMON_BAND) {
            candidates.push_back(p);
        }
    }
    return candidates;

}