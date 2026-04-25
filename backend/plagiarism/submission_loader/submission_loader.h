#pragma once

#include <string>
#include <vector>
#include "../models/submission.h"
#include "../models/programming_language.h"

class SubmissionLoader {
public:
    static std::vector<Submission> load_from_directory(const std::string& root_dir);

    static std::vector<Submission> load_problem_submissions(
        const std::string& root_dir,
        const std::vector<std::string>& problem_letters
    );

    static Submission load_submission(const std::string& id, const std::string& file_path);

private:
    static ProgrammingLanguage detect_language(const std::string& file_path);

    static std::string read_file_content(const std::string& file_path);
};

