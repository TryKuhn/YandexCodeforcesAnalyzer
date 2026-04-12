#pragma once

#include <vector>

#include "../models/submission.h"
#include "../models/similar_submission_pair.h"


std::vector<SimilarSubmissionPair> compute_similarity_pairs(
	const std::vector<Submission>& submissions,
	double threshold = 0.0
);
