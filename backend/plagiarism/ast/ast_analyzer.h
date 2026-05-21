#pragma once

#include <string>
#include "ast_features.h"
#include "ast_tree.h"

/// @brief Parses a C++ source string and extracts structural AST features.
///
/// Counts top-level constructs (functions, ifs, loops, returns, calls) via
/// a single libclang traversal. Sets parse_ok to false when libclang reports
/// a fatal parse error.
///
/// @param code Normalized C++ source text.
/// @return AstFeatures populated from the parse result.
AstFeatures analyze_ast(const std::string& code);

/// @brief Parses a C++ source string and builds a simplified AST tree.
///
/// Constructs a typed tree of AstNode objects mirroring the libclang cursor
/// hierarchy. Sets parse_ok to false when libclang reports a fatal parse error.
///
/// @param code Normalized C++ source text.
/// @return AstTree with root populated; parse_ok reflects success.
AstTree build_ast_tree(const std::string& code);

/// @brief Parses source once and returns both AST features and tree.
///
/// More efficient than calling analyze_ast and build_ast_tree separately
/// because it performs only one libclang translation-unit parse.
///
/// @param code Normalized C++ source text.
/// @return Pair of (AstFeatures, AstTree).
std::pair<AstFeatures, AstTree> analyze_and_build_ast(const std::string& code);
