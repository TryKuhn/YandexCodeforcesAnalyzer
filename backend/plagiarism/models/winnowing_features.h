#pragma once
#include <cstdint>
#include <vector>

/// @brief Winnowing fingerprints and MinHash signature for a submission.
struct WinnowingFeatures {
    std::vector<std::uint64_t> fingerprints;
    std::vector<std::uint64_t> minhash_signature;
};