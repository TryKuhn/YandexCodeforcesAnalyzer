#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <unordered_set>

#include "ast_tree.h"

struct CallGraphFeatures {
    bool parse_ok = false;
    int functions_cnt = 0;
    int edges_cnt = 0;

    std::unordered_map<std::uint64_t, int> edge_hash_freq;
    std::unordered_map<int, int> in_degree_hist;
    std::unordered_map<int, int> out_degree_hist;
};

CallGraphFeatures BuildCallGraphFeatures(const AstTree& tree);

