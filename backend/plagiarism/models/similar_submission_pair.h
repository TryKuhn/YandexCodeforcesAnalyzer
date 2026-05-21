#pragma once

#include <string>

/// @brief A pair of submissions flagged as potentially plagiarized.
struct SimilarSubmissionPair {
    std::string first_submission_id;
    std::string second_submission_id;
    double plagiarism_percent = 0.0;

    std::string first_participant;
    std::string second_participant;

    std::string first_problem;
    std::string second_problem;

    std::string first_file_name;
    std::string second_file_name;

    std::string first_source_path;
    std::string second_source_path;
};