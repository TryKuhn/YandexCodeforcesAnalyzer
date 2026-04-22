#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

#include "ast_tree.h"

std::string AstNodeTypeToString(AstNodeType type);
std::string AstNodeRoleToString(AstNodeRole role);

std::uint64_t ComputeAstSubtreeHash(
    const AstNode* node,
    std::unordered_map<std::uint64_t, int>& subtree_hash_freq,
    int min_subtree_size = 2
);

std::unordered_map<std::uint64_t, int> BuildAstSubtreeHashFreq(
    const AstTree& tree,
    int min_subtree_size = 2
);

std::vector<std::string> BuildAstNormalizedSequencePreorder(const AstTree& tree);

void CollectAstNormalizedSequencePreorder(
    const AstNode* node,
    std::vector<std::string>& ret
);

