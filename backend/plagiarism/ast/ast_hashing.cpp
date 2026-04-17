#include "ast_hashing.h"

#include <boost/functional/hash.hpp>

#include <cstddef>

std::string AstNodeTypeToString(AstNodeType type) {
    if (type == AstNodeType::kTranslationUnit) return "TranslationUnit";
    if (type == AstNodeType::kFunctionDecl) return "FunctionDecl";
    if (type == AstNodeType::kParamDecl) return "ParamDecl";
    if (type == AstNodeType::kVarDecl) return "VarDecl";
    if (type == AstNodeType::kCompoundStmt) return "CompoundStmt";
    if (type == AstNodeType::kIfStmt) return "IfStmt";
    if (type == AstNodeType::kForStmt) return "ForStmt";
    if (type == AstNodeType::kWhileStmt) return "WhileStmt";
    if (type == AstNodeType::kReturnStmt) return "ReturnStmt";
    if (type == AstNodeType::kCallExpr) return "CallExpr";
    if (type == AstNodeType::kBinaryOp) return "BinaryOp";
    if (type == AstNodeType::kUnaryOp) return "UnaryOp";
    if (type == AstNodeType::kDeclRefExpr) return "DeclRefExpr";
    if (type == AstNodeType::kIntegerLiteral) return "IntegerLiteral";
    if (type == AstNodeType::kFloatLiteral) return "FloatLiteral";
    if (type == AstNodeType::kStringLiteral) return "StringLiteral";
    return "Unknown";
}

std::string AstNodeRoleToString(AstNodeRole role) {
    if (role == AstNodeRole::kNone) return "None";
    if (role == AstNodeRole::kCondition) return "Condition";
    if (role == AstNodeRole::kBody) return "Body";
    if (role == AstNodeRole::kInit) return "Init";
    if (role == AstNodeRole::kUpdate) return "Update";
    if (role == AstNodeRole::kCallee) return "Callee";
    if (role == AstNodeRole::kArgument) return "Argument";
    if (role == AstNodeRole::kLeft) return "Left";
    if (role == AstNodeRole::kRight) return "Right";
    return "Unknown";
}

static std::uint64_t HashNodeParams(const AstNode* node) {
    std::size_t seed = 0;
    boost::hash_combine(seed, static_cast<int>(node->type));
    boost::hash_combine(seed, static_cast<int>(node->role));

    if (node->type == AstNodeType::kIntegerLiteral ||
        node->type == AstNodeType::kFloatLiteral ||
        node->type == AstNodeType::kStringLiteral) {
        boost::hash_combine(seed, "LITERAL");
    } else if (node->type == AstNodeType::kDeclRefExpr) {
        boost::hash_combine(seed, "REF");
    } else if (node->type == AstNodeType::kVarDecl || node->type == AstNodeType::kParamDecl) {
        boost::hash_combine(seed, "DECL");
    }

    return static_cast<std::uint64_t>(seed);
}

std::uint64_t ComputeAstSubtreeHash(
    const AstNode* node,
    std::unordered_map<std::uint64_t, int>& subtree_hash_freq,
    int min_subtree_size
) {
    if (node == nullptr) {
        return 0;
    }

    std::uint64_t seed = HashNodeParams(node);
    for (const auto& child : node->children) {
        const std::uint64_t child_hash = ComputeAstSubtreeHash(child.get(), subtree_hash_freq, min_subtree_size);
        boost::hash_combine(seed, child_hash);
    }

    bool is_deep_and_small = (node->depth > 8 && node->subtree_size < 5);
    if (node->subtree_size >= min_subtree_size && !is_deep_and_small) {
        subtree_hash_freq[seed]++;
    }
    return seed;
}

std::unordered_map<std::uint64_t, int> BuildAstSubtreeHashFreq(
    const AstTree& tree,
    int min_subtree_size
) {
    std::unordered_map<std::uint64_t, int> freq;
    if (!tree.parse_ok || tree.root == nullptr) {
        return freq;
    }
    ComputeAstSubtreeHash(tree.root.get(), freq, min_subtree_size);
    return freq;
}

static void CollectAstNormalizedSequencePreorder(
    const AstNode* node,
    std::vector<std::string>& ret,
    int min_subtree_size = 2
) {
    if (node == nullptr) {
        return;
    }

    if (node->subtree_size < min_subtree_size) {
        return;
    }

    ret.push_back(AstNodeTypeToString(node->type));

    for (auto& child : node->children) {
        CollectAstNormalizedSequencePreorder(child.get(), ret, min_subtree_size);
    }
}

std::vector<std::string> BuildAstNormalizedSequencePreorder(const AstTree& tree) {
    std::vector<std::string> ret;
    if (!tree.parse_ok || tree.root == nullptr) {
        return ret;
    }
    CollectAstNormalizedSequencePreorder(tree.root.get(), ret, 3);
    return ret;
}

