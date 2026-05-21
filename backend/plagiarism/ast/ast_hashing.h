#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

#include "ast_tree.h"

/// @brief Converts an AstNodeType enum value to its canonical string name.
/// @param type AST node type enum value.
/// @return Human-readable type name string (e.g. `"FunctionDecl"`).
std::string AstNodeTypeToString(AstNodeType type);

/// @brief Converts an AstNodeRole enum value to its canonical string name.
/// @param role AST node role enum value.
/// @return Human-readable role name string (e.g. `"Condition"`).
std::string AstNodeRoleToString(AstNodeRole role);

/// @brief Recursively computes the structural hash of an AST subtree.
///
/// Hashes are computed bottom-up: each node's hash is derived from its
/// type, role, and the hashes of its children. Subtrees with at least
/// min_subtree_size nodes are recorded in subtree_hash_freq.
///
/// @param node              Root of the subtree to hash.
/// @param subtree_hash_freq Map updated in-place with hash → count entries.
/// @param min_subtree_size  Minimum subtree size to record. Default 2.
/// @return 64-bit structural hash of the subtree rooted at node.
std::uint64_t ComputeAstSubtreeHash(
    const AstNode* node,
    std::unordered_map<std::uint64_t, int>& subtree_hash_freq,
    int min_subtree_size = 2
);

/// @brief Builds a subtree hash frequency map for an entire AST.
///
/// Calls ComputeAstSubtreeHash from the tree root.
///
/// @param tree             Parsed AST tree.
/// @param min_subtree_size Minimum subtree node count to record. Default 2.
/// @return Map of subtree hash → occurrence count.
std::unordered_map<std::uint64_t, int> BuildAstSubtreeHashFreq(
    const AstTree& tree,
    int min_subtree_size = 2
);

/// @brief Builds a preorder sequence of normalized node-kind strings.
///
/// Each entry encodes the node's type and role as `"Type:Role"`.
/// The sequence is used for 3-gram similarity comparison.
///
/// @param tree Parsed AST tree.
/// @return Preorder sequence of node-kind strings.
std::vector<std::string> BuildAstNormalizedSequencePreorder(const AstTree& tree);

/// @brief Recursively collects preorder node-kind strings into a vector.
///
/// Helper called by BuildAstNormalizedSequencePreorder; exposed for testing.
///
/// @param node Root of the subtree to traverse.
/// @param ret  Output vector appended to in-place.
void CollectAstNormalizedSequencePreorder(
    const AstNode* node,
    std::vector<std::string>& ret
);

