#pragma once

#include <string>
#include "ast_features.h"
#include "ast_tree.h"

AstFeatures analyze_ast(const std::string& code);
AstTree build_ast_tree(const std::string& code);
std::pair<AstFeatures, AstTree> analyze_and_build_ast(const std::string& code);
