#pragma once

#include <string>
#include <unordered_map>
#include <vector>

struct AstFeatures {
    bool parse_ok = false;

    int functions_cnt = 0;
    int ifs_cnt = 0;
    int fors_cnt = 0;
    int whiles_cnt = 0;
    int returns_cnt = 0;
    int calls_cnt = 0;

    int max_depth = 0;

    std::unordered_map<std::string, int> kind_freq;
    std::vector<std::string> preorder_kinds;
};