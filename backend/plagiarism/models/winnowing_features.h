#pragma once
#include <cstdint>
#include <vector>

struct WinnowingFeatures {
    std::vector<std::uint64_t> fingerprints;
    std::vector<std::uint64_t> minhash_signature;
};