#pragma once

#include <string>

struct SimilarSubmissionPair {
    int first_submission_id = 0;
    int second_submission_id = 0;
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