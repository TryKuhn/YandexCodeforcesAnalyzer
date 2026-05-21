#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

/// @brief Coarse-grained type classification of an AST node.
enum class AstNodeType {
    kTranslationUnit,
    kFunctionDecl,
    kParamDecl,
    kVarDecl,
    kCompoundStmt,
    kIfStmt,
    kForStmt,
    kWhileStmt,
    kReturnStmt,
    kCallExpr,
    kBinaryOp,
    kUnaryOp,
    kDeclRefExpr,
    kIntegerLiteral,
    kFloatLiteral,
    kStringLiteral,
    kUnknown,
};

/// @brief Semantic role a node plays in its parent's construct.
enum class AstNodeRole {
    kNone,
    kCondition,
    kBody,
    kInit,
    kUpdate,
    kCallee,
    kArgument,
    kLeft,
    kRight,
    kUnknown,
};

/// @brief Inclusive source line range for a node.
struct LineRange {
    int start_line = 0;
    int end_line = 0;
};

/// @brief Single node in the simplified AST used for similarity scoring.
struct AstNode {
    AstNodeType type = AstNodeType::kUnknown;
    AstNodeRole role = AstNodeRole::kNone;

    std::string raw_name;
    std::string normalized_value;
    std::string usr;

    LineRange line_range;

    AstNode* parent = nullptr;
    std::vector<std::unique_ptr<AstNode>> children;

    int depth = 0;
    int subtree_size = 1;
};

/// @brief Root container for a parsed AST.
struct AstTree {
    bool parse_ok = false;
    std::unique_ptr<AstNode> root;
};

