#pragma once

#include "../models/submission.h"
#include "../models/submission_data.h"
#include "../models/submission_data.h"
#include "../models/submission_features.h"

SubmissionFeatures BuildSubmissionFeatures(const SubmissionData& representation);
SubmissionData BuildSubmissionData(const Submission& submission);