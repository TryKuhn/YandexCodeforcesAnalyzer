#include "winnowing.h"

#include <algorithm>
#include <limits>

std::uint64_t splitmix64(std::uint64_t x) {
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}

static std::uint64_t get_kgram_hash(const std::string& str) {
    std::uint64_t hash = kFnv1aOffsetBasis;
    for (unsigned char c : str) {
        hash ^= static_cast<std::uint64_t>(c);
        hash *= kFnv1aPrime;
    }
    return splitmix64(hash);
}

std::vector<std::uint64_t> build_kgram_hashes(
    const std::vector<std::string>& token_texts,
    std::size_t k
) {
    if (token_texts.size() < k) {
        std::string ret;
        for (std::size_t j = 0; j < token_texts.size(); j++) {
            if (j > 0) ret += "|";
            ret += token_texts[j];
        }
        return {get_kgram_hash(ret)};
    }
    std::vector<std::uint64_t> hashes;
    for (std::size_t i = 0; i + k - 1 < token_texts.size(); i++) {
        std::string kgram;
        for (std::size_t j = 0; j < k; j++) {
            if (j > 0) kgram += "|";
            kgram += token_texts[i + j];
        }
        hashes.push_back(get_kgram_hash(kgram));
    }
    return hashes;
}

std::vector<std::uint64_t> run_winnowing(
    const std::vector<std::uint64_t>& hashes,
    std::size_t window
) {
    std::vector<std::uint64_t> fingerprints;
    if (hashes.size() < window) {
        return {*std::min_element(hashes.begin(), hashes.end())};
    }
    for (std::size_t i = 0; i + window - 1 < hashes.size(); i++) {
        std::uint64_t min_hash = hashes[i];
        for (std::size_t j = 1; j < window; j++) {
            min_hash = std::min(min_hash, hashes[i + j]);
        }
        fingerprints.push_back(min_hash);
    }
    std::vector<std::uint64_t> compressed;
    for (auto h : fingerprints) {
        if (compressed.empty() || compressed.back() != h) {
            compressed.push_back(h);
        }
    }
    return compressed;
}

std::vector<std::uint64_t> build_minhash_signature(const std::vector<std::uint64_t>& fingerprints) {
    std::vector<std::uint64_t> ret;
    for (size_t i = 0; i < MINHASH_SIZE; i++) {
        std::uint64_t min_hash = std::numeric_limits<std::uint64_t>::max();

        for (auto h : fingerprints) {
            min_hash = std::min(min_hash, splitmix64(h ^ i));
        }
        ret.push_back(min_hash);
    }
    return ret;
}
