#pragma once

#include <string>
#include <unordered_map>
#include <vector>

struct TokenFeatures {
    int tokens_cnt = 0;
    int literals_cnt = 0;
    int punctuations_cnt = 0;
    int keywords_cnt = 0;
    int identifiers_cnt = 0;

    int unique_tokens = 0;

    std::unordered_map<std::string, int> freq;
    std::vector<std::string> grams3;
};