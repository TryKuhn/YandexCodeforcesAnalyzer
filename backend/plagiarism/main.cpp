#include <chrono>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

#include "models/submission.h"
#include "similarity/compare_submissions.h"
#include "submission_loader/submission_loader.h"

int main(int argc, char* argv[]) {
    auto start = std::chrono::steady_clock::now();

    if (argc < 3 || std::string(argv[1]) != "--load-from") {
        std::cerr << "Usage:\n";
        std::cerr << "  " << argv[0] << " --load-from <root_dir> [problem]\n";
        return 1;
    }

    const std::string root_dir = argv[2];
    const std::string problem = (argc > 3) ? argv[3] : "";

    std::vector<Submission> submissions;

    std::cout << "Loading submissions from: " << root_dir << "\n";
    if (!problem.empty()) {
        std::cout << "Problem: " << problem << "\n";
        submissions = SubmissionLoader::load_problem_submissions(root_dir, problem);
    } else {
        submissions = SubmissionLoader::load_from_directory(root_dir);
    }

    std::cout << "Loaded " << submissions.size() << " submissions\n";

    const std::vector<SimilarSubmissionPair> pairs =
        compute_similarity_pairs(submissions, 0.0);

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "Found pairs: " << pairs.size() << "\n";

    for (const auto& p : pairs) {
        std::cout
            << p.first_submission_id
            << " (" << p.first_participant
            << "/" << (p.first_problem.empty() ? "[no task]" : p.first_problem)
            << "/" << p.first_file_name << ")"
            << "  <->  "
            << p.second_submission_id
            << " (" << p.second_participant
            << "/" << (p.second_problem.empty() ? "[no task]" : p.second_problem)
            << "/" << p.second_file_name << ")"
            << "  =>  " << p.plagiarism_percent << "%\n";
    }

    auto finish = std::chrono::steady_clock::now();
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(finish - start).count();

    std::cout << "Total time: " << ms << " ms\n";
    return 0;
}