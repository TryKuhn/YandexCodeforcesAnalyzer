#include "lsh.h"
#include <boost/functional/hash.hpp>
#include <cstdint>
#include <utility>
#include <unordered_map>
#include <iostream>

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
    std::size_t operator()(const std::pair<std::string, std::string>& p) const noexcept {
        std::size_t seed = 0;
        boost::hash_combine(seed, p.first);
        boost::hash_combine(seed, p.second);
        return seed;
    }
};
std::vector<std::pair < std::string, std::string > > generate_lsh_candidate_pairs(
    const std::vector<SubmissionData>& prepared
) {
    std::vector < std:: pair < std::string, std::string > > candidates;

    std::unordered_map<std::uint64_t, std::vector<std::string>> buckets;
    std::unordered_map<std::pair < std::string, std::string >, int, PairHash > in_one_bucket_cnt;
    for (auto& to : prepared) {
        for (size_t band = 0; band < BANDS; band++) {
            std::uint64_t bucket_key = build_lsh_bucket_key(
                to.winnowing_features.minhash_signature,
                band * ROWS_PER_BAND
            );
            buckets[bucket_key].push_back(to.submission_id);
        }
    }

    std::cout << "\n--- LSH BUCKET STATS ---\n";
    std::cout << "Total buckets: " << buckets.size() << "\n";
    int buckets_size_1 = 0;
    int buckets_size_small = 0; 
    int buckets_size_huge = 0;  
    int max_bucket_size = 0;
    
    for (const auto& [hashh, indexes] : buckets) {
        max_bucket_size = std::max(max_bucket_size, (int)indexes.size());
        if (indexes.size() == 1) buckets_size_1++;
        else if (indexes.size() <= MAX_BUCKET_SIZE) buckets_size_small++;
        else buckets_size_huge++;
    }
    
    std::cout << "Buckets with 1 item: " << buckets_size_1 << "\n";
    std::cout << "Buckets with 2 to " << MAX_BUCKET_SIZE << " items (processed): " << buckets_size_small << "\n";
    std::cout << "Buckets with > " << MAX_BUCKET_SIZE << " items (ignored): " << buckets_size_huge << "\n";
    std::cout << "Max bucket size: " << max_bucket_size << "\n";
    std::cout << "------------------------\n";

    for (auto& [hashh, indexes] : buckets) {
        if (indexes.size() > MAX_BUCKET_SIZE) {
            continue;
        }
        for (size_t i = 0; i < indexes.size(); i++) {
            for (size_t j = i + 1; j < indexes.size(); j++) {
                std::pair < std::string, std::string > p = {std::min(indexes[i], indexes[j]), std::max(indexes[i], indexes[j])};
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