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

std::uint64_t build_lsh_bucket_key(
    const std::vector<std::uint64_t>& signature,
    std::size_t start,
    int rows_per_band = ROWS_PER_BAND
);

std::vector<std:: pair < std::string, std::string > > generate_lsh_candidate_pairs(
    const std::vector<SubmissionData>& prepared
);

