#include "submission_loader.h"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <iostream>

namespace fs = std::filesystem;

namespace {

bool is_supported_source_file(const fs::path& path) {
    const std::string ext = path.extension().string();
    return ext == ".cpp" || ext == ".cc" || ext == ".cxx" || ext == ".c++" || ext == ".py";
}

void load_submissions_from_directory(
    const fs::path& dir,
    const std::string& participant,
    const std::string& problem,
    std::vector<Submission>& submissions,
    int& submission_id
) {
    if (!fs::exists(dir) || !fs::is_directory(dir)) {
        return;
    }

    for (const auto& file_entry : fs::directory_iterator(dir)) {
        if (!file_entry.is_regular_file()) continue;

        if (!is_supported_source_file(file_entry.path())) continue;

        Submission sub = SubmissionLoader::load_submission(std::to_string(submission_id), file_entry.path().string());
        sub.participant = participant;
        sub.problem = problem;
        sub.file_name = file_entry.path().filename().string();
        sub.source_path = file_entry.path().string();
        submissions.push_back(sub);
        ++submission_id;
    }
}

}

ProgrammingLanguage SubmissionLoader::detect_language(const std::string& file_path) {
    std::string ext = fs::path(file_path).extension().string();

    if (ext == ".cpp" || ext == ".cc" || ext == ".cxx" || ext == ".c++") {
        return ProgrammingLanguage::Cpp;
    }
    if (ext == ".py") {
        return ProgrammingLanguage::Python;
    }

    return ProgrammingLanguage::Unknown;
}

std::string SubmissionLoader::read_file_content(const std::string& file_path) {
    std::ifstream file(file_path);
    if (!file.is_open()) {
        std::cerr << "Error: Cannot open file " << file_path << std::endl;
        return "";
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    return buffer.str();
}

Submission SubmissionLoader::load_submission(const std::string& id, const std::string& file_path) {
    Submission sub;
    sub.id = id;
    sub.language = detect_language(file_path);
    sub.rawCode = read_file_content(file_path);
    return sub;
}

std::vector<Submission> SubmissionLoader::load_from_directory(const std::string& root_dir) {
    std::vector<Submission> submissions;

    if (!fs::exists(root_dir)) {
        std::cerr << "Error: Directory " << root_dir << " does not exist" << std::endl;
        return submissions;
    }

    int submission_id = 1;

    for (const auto& user_entry : fs::directory_iterator(root_dir)) {
        if (!user_entry.is_directory()) continue;

        const std::string participant = user_entry.path().filename().string();
        load_submissions_from_directory(user_entry.path(), participant, "", submissions, submission_id);

        for (const auto& entry : fs::directory_iterator(user_entry.path())) {
            if (!entry.is_directory()) continue;

            const std::string problem = entry.path().filename().string();
            load_submissions_from_directory(entry.path(), participant, problem, submissions, submission_id);
        }
    }

    return submissions;
}

std::vector<Submission> SubmissionLoader::load_problem_submissions(
    const std::string& root_dir,
    const std::vector<std::string>& problem_letters
) {
    std::vector<Submission> submissions;

    if (!fs::exists(root_dir)) {
        std::cerr << "Error: Directory " << root_dir << " does not exist" << std::endl;
        return submissions;
    }

    int submission_id = 1;

    for (const auto& user_entry : fs::directory_iterator(root_dir)) {
        if (!user_entry.is_directory()) continue;

        const std::string participant = user_entry.path().filename().string();
        
        for (const auto& file_entry : fs::directory_iterator(user_entry.path())) {
            if (!file_entry.is_regular_file()) continue;
            
            std::string filename = file_entry.path().filename().string();
            
            for (const std::string& problem_letter : problem_letters) {
                // Ищем префикс "B-" или "C-" и т.д.
                if (filename.rfind(problem_letter + "-", 0) == 0) {
                    if (!is_supported_source_file(file_entry.path())) break;
                    
                    Submission sub = SubmissionLoader::load_submission(std::to_string(submission_id), file_entry.path().string());
                    sub.participant = participant;
                    sub.problem = problem_letter;
                    sub.file_name = filename;
                    sub.source_path = file_entry.path().string();
                    submissions.push_back(sub);
                    ++submission_id;
                    break;
                }
            }
        }
    }

    return submissions;
}

