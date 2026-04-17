#include "submission_stages.h"

#include "../ast/ast_hashing.h"
#include "../ast/ast_analyzer.h"
#include "../preprocessing/normalize.h"
#include "../preprocessing/llvm_ir_pipeline.h"
#include "../tokenizer/normalize_tokens.h"
#include "../tokenizer/token_features_builder.h"
#include "../tokenizer/tokenizer.h"

std::string BuildSubmissionAstCode(const Submission& submission) {
    return NormalizeForAST(submission.rawCode);
}

std::string BuildSubmissionTokenCode(const Submission& submission) {
    return NormalizeForTokenizer(submission.rawCode);
}

std::string BuildSubmissionIrCode(const std::string& normalized_code) {
    if (normalized_code.empty()) {
        return "";
    }

    const std::string prelude =
        "#include <bits/stdc++.h>\n"
        "using namespace std;\n";

    return BuildLlvmIrFromCode(prelude + normalized_code);
}

std::vector<Token> BuildSubmissionTokens(const std::string& token_code) {
    return TokenizerWithClang(token_code);
}

std::vector<Token> BuildNormalizedSubmissionTokens(const std::vector<Token>& tokens) {
    return NormalizeTokens(tokens);
}

std::vector<std::string> BuildNormalizedTokenTexts(
    const std::vector<Token>& normalized_tokens
) {
    return TextTokens(normalized_tokens);
}

TokenFeatures BuildSubmissionTokenFeatures(
    const std::vector<Token>& raw_tokens,
    const std::vector<Token>& normalized_tokens
) {
    return BuildTokenFeatures(raw_tokens, normalized_tokens);
}

AstFeatures BuildSubmissionAstFeatures(const std::string& ast_code) {
    return analyze_ast(ast_code);
}

AstTree BuildSubmissionAstTree(const std::string& ast_code) {
    return build_ast_tree(ast_code);
}


std::unordered_map<std::uint64_t, int> BuildSubmissionAstSubtreeHashFreq(
    const AstTree& tree,
    int min_subtree_size
) {
    return BuildAstSubtreeHashFreq(tree, min_subtree_size);
}

std::vector<std::string> BuildSubmissionAstNormalizedSequence(const AstTree& tree) {
    return BuildAstNormalizedSequencePreorder(tree);
}
