#pragma once

#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

#include "../models/submission_data.h"
#include "winnowing.h"

const int BANDS = 32;
const int ROWS_PER_BAND = 4;
const int MIN_COMMON_BAND = 1;
const std::size_t MAX_BUCKET_SIZE = 2000;

/// @brief Hashes a contiguous band of a MinHash signature into a single bucket key.
///
/// Seeds the hash chain with `band` so that equal signature values in
/// different bands produce distinct bucket keys (preventing cross-band
/// collisions in the shared `buckets` map).
///
/// @param signature     Full MinHash signature of a submission.
/// @param band          Zero-based band index used as the hash seed.
/// @param rows_per_band Number of rows to fold. Defaults to ROWS_PER_BAND.
/// @return 64-bit bucket key for the band.
std::uint64_t build_lsh_bucket_key(
    const std::vector<std::uint64_t>& signature,
    std::size_t band,
    int rows_per_band = ROWS_PER_BAND
);

/// @brief Generates candidate submission pairs via LSH banding.
///
/// Submissions that share at least MIN_COMMON_BAND bucket collisions are
/// emitted as candidate pairs for full similarity scoring. Buckets larger
/// than MAX_BUCKET_SIZE are skipped to avoid quadratic blowup on near-uniform
/// signatures.
///
/// @param prepared Submissions with precomputed MinHash signatures.
/// @return Deduplicated list of (id_a, id_b) candidate pairs.
std::vector<std::pair<std::string, std::string>> generate_lsh_candidate_pairs(
    const std::vector<SubmissionData>& prepared
);

