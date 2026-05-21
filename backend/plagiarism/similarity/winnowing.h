#pragma once
#include <cstdint>
#include <string>
#include <vector>

inline constexpr std::uint64_t kFnv1aOffsetBasis = 1469598103934665603ULL;
inline constexpr std::uint64_t kFnv1aPrime = 1099511628211ULL;

/// @brief Applies the splitmix64 finalizer to avalanche hash bits.
/// @param x Input 64-bit value.
/// @return Finalized 64-bit hash.
std::uint64_t splitmix64(std::uint64_t x);

inline constexpr std::size_t MINHASH_SIZE = 128;

inline constexpr std::size_t KGRAM = 5;

/// @brief Sliding window size for the winnowing fingerprint selection step.
///
/// Guarantees that any token match of length ≥ KGRAM × WINNOWING_WINDOW is
/// represented by at least one shared fingerprint.
inline constexpr std::size_t WINNOWING_WINDOW = KGRAM;

/// @brief Builds FNV-1a hashes for every k-gram in a token sequence.
///
/// Consecutive runs of `k` token texts are concatenated and hashed.
/// Sequences shorter than `k` produce an empty vector.
///
/// @param token_texts Ordered list of normalized token text strings.
/// @param k           K-gram width. Defaults to KGRAM.
/// @return Vector of k-gram hashes, one per sliding window position.
std::vector<std::uint64_t> build_kgram_hashes(
    const std::vector<std::string>& token_texts,
    std::size_t k = KGRAM
);

/// @brief Selects fingerprints via the winnowing algorithm.
///
/// Within each sliding window of size `window`, retains the minimum hash
/// value. Duplicates from overlapping windows are deduplicated.
///
/// @param hashes Input k-gram hash vector.
/// @param window Sliding window size.
/// @return Deduplicated fingerprint set.
std::vector<std::uint64_t> run_winnowing(
    const std::vector<std::uint64_t>& hashes,
    std::size_t window
);

/// @brief Builds a MinHash signature of size MINHASH_SIZE from a fingerprint set.
///
/// Uses MINHASH_SIZE independent hash functions derived from splitmix64
/// permutations of the input fingerprints.
///
/// @param fingerprints Winnowing fingerprint set.
/// @return MinHash signature vector of length MINHASH_SIZE.
std::vector<std::uint64_t> build_minhash_signature(const std::vector<std::uint64_t>& fingerprints);