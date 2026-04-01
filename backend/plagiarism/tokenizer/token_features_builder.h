#pragma once

#include <vector>

#include "../models/token.h"
#include "../models/token_features.h"

TokenFeatures BuildTokenFeatures(const std::vector<Token>& raw_tokens,
    const std::vector<Token>& normalized_tokens);