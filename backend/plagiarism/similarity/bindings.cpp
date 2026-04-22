#include<pybind11/pybind11.h>
#include<pybind11/stl.h>

#include "compare_submissions.h"
#include<models/submission.h>

#include<string>
#include<vector>

namespace py = pybind11;

py::list compute_similarity_pairs_py(py::list submissions, double threshold) {
    std::vector<Submission> subs;
    for (const auto& item : submissions) {
        subs.push_back(item.cast<Submission>());
    }

    const auto pairs = compute_similarity_pairs(subs, threshold);
    py::list ret;
    for (const auto& pair : pairs) {
         py::dict d;
         d["first_submission_id"] = pair.first_submission_id;
         d["second_submission_id"] = pair.second_submission_id;
         d["plagiarism_percent"] = pair.plagiarism_percent;
         ret.append(d);
    }
    return ret;
}
PYBIND11_MODULE(plagiarism_cpp, m) {
    m.doc() = "Python bindings for plagiarism";
    m.def("compute_similarity_pairs",
          &compute_similarity_pairs_py,
          py::arg("submissions"),
          py::arg("threshold"),
          "Compute plagiarism similarity pairs" );
}
