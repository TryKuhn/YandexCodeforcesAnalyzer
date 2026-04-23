#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "compare_submissions.h"
#include <models/submission.h>
#include <models/similar_submission_pair.h>

namespace py = pybind11;

PYBIND11_MODULE(plagiarism_cpp, m) {
    py::enum_<ProgrammingLanguage>(m, "ProgrammingLanguage")
        .value("Cpp", ProgrammingLanguage::Cpp)
        .value("Python", ProgrammingLanguage::Python)
        .value("Unknown", ProgrammingLanguage::Unknown)
        .export_values();

    py::class_<Submission>(m, "Submission")
        .def(py::init<>())
        .def_readwrite("id", &Submission::id)
        .def_readwrite("language", &Submission::language)
        .def_readwrite("rawCode", &Submission::rawCode)
        .def_readwrite("participant", &Submission::participant)
        .def_readwrite("problem", &Submission::problem)
        .def_readwrite("file_name", &Submission::file_name)
        .def_readwrite("source_path", &Submission::source_path);

    py::class_<SimilarSubmissionPair>(m, "SimilarSubmissionPair")
        .def_readonly("first_submission_id", &SimilarSubmissionPair::first_submission_id)
        .def_readonly("second_submission_id", &SimilarSubmissionPair::second_submission_id)
        .def_readonly("plagiarism_percent", &SimilarSubmissionPair::plagiarism_percent)
        .def_readonly("first_participant", &SimilarSubmissionPair::first_participant)
        .def_readonly("second_participant", &SimilarSubmissionPair::second_participant)
        .def_readonly("first_problem", &SimilarSubmissionPair::first_problem)
        .def_readonly("second_problem", &SimilarSubmissionPair::second_problem)
        .def_readonly("first_file_name", &SimilarSubmissionPair::first_file_name)
        .def_readonly("second_file_name", &SimilarSubmissionPair::second_file_name)
        .def_readonly("first_source_path", &SimilarSubmissionPair::first_source_path)
        .def_readonly("second_source_path", &SimilarSubmissionPair::second_source_path);

    m.def(
        "compute_similarity_pairs",
        &compute_similarity_pairs,
        py::arg("submissions"),
        py::arg("threshold")
    );
}