#pragma once
#include <cstdint>
#include <string>
#include <vector>

inline constexpr std::uint64_t kFnv1aOffsetBasis = 1469598103934665603ULL;
inline constexpr std::uint64_t kFnv1aPrime = 1099511628211ULL;

std::uint64_t splitmix64(std::uint64_t x);

inline constexpr std::size_t MINHASH_SIZE = 128;

std::uint64_t get_kgram_hash(const std::string& str);

const size_t KGRAM = 5;

std::vector<std::uint64_t> build_kgram_hashes(
    const std::vector<std::string>& token_texts,
    int k = KGRAM
);

std::vector<std::uint64_t> run_winnowing(
    const std::vector<std::uint64_t>& hashes,
    int window
);

std::vector < uint64_t > build_minhash_signature(const std::vector<std::uint64_t>& fingerprints);