#pragma once

#include "../models/submission.h"
#include "../models/submission_data.h"

// Full build: tokenization + minhash + AST (used when all features needed upfront).
SubmissionData BuildSubmissionData(const Submission& submission);

// Cheap build: tokenization + minhash only, no AST parsing.
// Call EnrichWithAst() later for submissions that need full similarity scoring.
SubmissionData BuildSubmissionDataCheap(const Submission& submission);

// Adds AST features to a SubmissionData built with BuildSubmissionDataCheap().
void EnrichWithAst(SubmissionData& dat);