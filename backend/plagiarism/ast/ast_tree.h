#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

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

struct LineRange {
    int start_line = 0;
    int end_line = 0;
};

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

struct AstTree {
    bool parse_ok = false;
    std::unique_ptr<AstNode> root;
};

