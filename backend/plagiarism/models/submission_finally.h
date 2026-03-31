#pragma once
#include<string>
#include <vector>

#include "submission.h"
#include "submission_data.h"
#include "submission_features.h"

struct SubmissionFinally {
    Submission submission;
    SubmissionData submission_data;
    SubmissionFeatures submission_features;
};
