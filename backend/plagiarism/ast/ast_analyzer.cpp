#include "ast_analyzer.h"

#include <clang-c/Index.h>

#include <algorithm>
#include <string>
#include <unordered_map>
#include <utility>

static std::string to_std_string(CXString cx_string) {
    const char* c_str = clang_getCString(cx_string);
    std::string result;
    if (c_str) {
        result = c_str;
    } else {
        result = "";
    }
    clang_disposeString(cx_string);
    return result;
}

static std::string get_kind_name(CXCursor cursor) {
    CXCursorKind kind = clang_getCursorKind(cursor);
    return to_std_string(clang_getCursorKindSpelling(kind));
}

static bool is_from_main_file(CXCursor cursor) {
    CXSourceLocation location = clang_getCursorLocation(cursor);
    return clang_Location_isFromMainFile(location) != 0;
}

static bool is_transparent_wrapper_kind(CXCursorKind kind) {
    if (kind == CXCursor_ParenExpr) return true;
    if (kind == CXCursor_UnexposedExpr) return true;
    return false;
}

static bool is_interesting_kind(CXCursorKind kind) {
    if (kind == CXCursor_FunctionDecl) return true;
    if (kind == CXCursor_IfStmt) return true;
    if (kind == CXCursor_ForStmt) return true;
    if (kind == CXCursor_WhileStmt) return true;
    if (kind == CXCursor_ReturnStmt) return true;
    if (kind == CXCursor_CallExpr) return true;
    return false;
}

static void count_interesting_kind(CXCursorKind kind, AstFeatures& features) {
    if (kind == CXCursor_FunctionDecl) {
        ++features.functions_cnt;
    } else if (kind == CXCursor_IfStmt) {
        ++features.ifs_cnt;
    } else if (kind == CXCursor_ForStmt) {
        ++features.fors_cnt;
    } else if (kind == CXCursor_WhileStmt) {
        ++features.whiles_cnt;
    } else if (kind == CXCursor_ReturnStmt) {
        ++features.returns_cnt;
    } else if (kind == CXCursor_CallExpr) {
        ++features.calls_cnt;
    }
}

static AstNodeType convert_kind(CXCursorKind kind) {
    if (kind == CXCursor_TranslationUnit) return AstNodeType::kTranslationUnit;
    if (kind == CXCursor_FunctionDecl) return AstNodeType::kFunctionDecl;
    if (kind == CXCursor_ParmDecl) return AstNodeType::kParamDecl;
    if (kind == CXCursor_VarDecl) return AstNodeType::kVarDecl;
    if (kind == CXCursor_CompoundStmt) return AstNodeType::kCompoundStmt;
    if (kind == CXCursor_IfStmt) return AstNodeType::kIfStmt;
    if (kind == CXCursor_ForStmt) return AstNodeType::kForStmt;
    if (kind == CXCursor_WhileStmt) return AstNodeType::kWhileStmt;
    if (kind == CXCursor_ReturnStmt) return AstNodeType::kReturnStmt;
    if (kind == CXCursor_CallExpr) return AstNodeType::kCallExpr;
    if (kind == CXCursor_BinaryOperator) return AstNodeType::kBinaryOp;
    if (kind == CXCursor_UnaryOperator) return AstNodeType::kUnaryOp;
    if (kind == CXCursor_DeclRefExpr) return AstNodeType::kDeclRefExpr;
    if (kind == CXCursor_IntegerLiteral) return AstNodeType::kIntegerLiteral;
    if (kind == CXCursor_FloatingLiteral) return AstNodeType::kFloatLiteral;
    if (kind == CXCursor_StringLiteral) return AstNodeType::kStringLiteral;
    return AstNodeType::kUnknown;
}

static LineRange extract_line_range(CXCursor cursor) {
    LineRange line_range;

    CXSourceRange range = clang_getCursorExtent(cursor);
    CXSourceLocation begin = clang_getRangeStart(range);
    CXSourceLocation end = clang_getRangeEnd(range);

    unsigned begin_line = 0;
    unsigned end_line = 0;

    clang_getSpellingLocation(begin, nullptr, &begin_line, nullptr, nullptr);
    clang_getSpellingLocation(end, nullptr, &end_line, nullptr, nullptr);

    line_range.start_line = static_cast<int>(begin_line);
    line_range.end_line = static_cast<int>(end_line);
    return line_range;
}

static std::unique_ptr<AstNode> make_node(CXCursor cursor, AstNode* parent, int depth) {
    auto node = std::make_unique<AstNode>();
    node->type = convert_kind(clang_getCursorKind(cursor));
    node->role = AstNodeRole::kNone;
    node->raw_name = to_std_string(clang_getCursorSpelling(cursor));
    node->normalized_value = node->raw_name;
    node->usr = to_std_string(clang_getCursorUSR(cursor));
    node->line_range = extract_line_range(cursor);
    node->parent = parent;
    node->depth = depth;
    return node;
}

struct normalization_state {
    std::unordered_map<std::string, std::vector<std::string>> bindings;
    std::vector<std::vector<std::string>> scope_changes;
    std::vector<int> next_arg_stack;
    std::vector<int> next_var_stack;
};

static bool opens_scope(CXCursorKind kind) {
    if (kind == CXCursor_TranslationUnit) return true;
    if (kind == CXCursor_FunctionDecl) return true;
    if (kind == CXCursor_CompoundStmt) return true;
    if (kind == CXCursor_ForStmt) return true;
    if (kind == CXCursor_WhileStmt) return true;
    if (kind == CXCursor_IfStmt) return true;
    return false;
}

static void push_scope(normalization_state& state) {
    state.scope_changes.emplace_back();
}

static void pop_scope(normalization_state& state) {
    if (state.scope_changes.empty()) {
        return;
    }

    auto declared = std::move(state.scope_changes.back());
    state.scope_changes.pop_back();

    for (const std::string& raw_name : declared) {
        auto it = state.bindings.find(raw_name);
        if (it == state.bindings.end() || it->second.empty()) {
            continue;
        }
        it->second.pop_back();
        if (it->second.empty()) {
            state.bindings.erase(it);
        }
    }
}

static void push_function_counters(normalization_state& state) {
    state.next_arg_stack.push_back(0);
    state.next_var_stack.push_back(0);
}

static void pop_function_counters(normalization_state& state) {
    if (!state.next_arg_stack.empty()) {
        state.next_arg_stack.pop_back();
    }
    if (!state.next_var_stack.empty()) {
        state.next_var_stack.pop_back();
    }
}

static std::string lookup_normalized_name(const normalization_state& state, const std::string& raw_name) {
    auto it = state.bindings.find(raw_name);
    if (it == state.bindings.end() || it->second.empty()) {
        return "ID_GLOBAL";
    }
    return it->second.back();
}

static std::string declare_symbol(normalization_state& state, const std::string& raw_name, bool is_param) {
    if (state.scope_changes.empty()) {
        push_scope(state);
    }

    std::string label;
    if (is_param) {
        if (state.next_arg_stack.empty()) {
            state.next_arg_stack.push_back(0);
        }
        label = "ARG_" + std::to_string(state.next_arg_stack.back()++);
    } else {
        if (state.next_var_stack.empty()) {
            state.next_var_stack.push_back(0);
        }
        label = "VAR_" + std::to_string(state.next_var_stack.back()++);
    }

    state.bindings[raw_name].push_back(label);
    state.scope_changes.back().push_back(raw_name);
    return label;
}

static void normalize_node_value(CXCursorKind kind, AstNode& node, normalization_state& state) {
    if (kind == CXCursor_IntegerLiteral || kind == CXCursor_FloatingLiteral) {
        node.normalized_value = "NUM";
        return;
    }
    if (kind == CXCursor_StringLiteral) {
        node.normalized_value = "STR";
        return;
    }
    if (kind == CXCursor_ParmDecl) {
        node.normalized_value = declare_symbol(state, node.raw_name, true);
        return;
    }
    if (kind == CXCursor_VarDecl) {
        node.normalized_value = declare_symbol(state, node.raw_name, false);
        return;
    }
    if (kind == CXCursor_DeclRefExpr) {
        node.normalized_value = lookup_normalized_name(state, node.raw_name);
        return;
    }
    if (kind == CXCursor_FunctionDecl) {
        node.normalized_value = "FUNC";
        return;
    }
    if (kind == CXCursor_CallExpr) {
        node.normalized_value = "CALL";
        return;
    }

    node.normalized_value = node.raw_name;
}

static int fill_subtree_size(AstNode* node) {
    int size = 1;
    for (auto& child : node->children) {
        size += fill_subtree_size(child.get());
    }
    node->subtree_size = size;
    return size;
}

struct traverse_data {
    AstNode* parent = nullptr;
    AstFeatures* features = nullptr;
    normalization_state* normalization = nullptr;
    int depth = 0;
};

static void dfs_collect(CXCursor cursor, traverse_data& data);

static enum CXChildVisitResult for_kids(
    CXCursor cursor,
    CXCursor parent,
    CXClientData client_data
) {
    (void)parent;

    auto* data = static_cast<traverse_data*>(client_data);
    dfs_collect(cursor, *data);

    return CXChildVisit_Continue;
}

static void dfs_collect(CXCursor cursor, traverse_data& data) {
    CXCursorKind kind = clang_getCursorKind(cursor);

    if (kind != CXCursor_TranslationUnit && !is_from_main_file(cursor)) {
        return;
    }

    if (is_transparent_wrapper_kind(kind)) {
        clang_visitChildren(cursor, for_kids, &data);
        return;
    }

    if (data.features != nullptr) {
        data.features->max_depth = std::max(data.features->max_depth, data.depth);

        if (is_interesting_kind(kind)) {
            std::string kind_name = get_kind_name(cursor);

            count_interesting_kind(kind, *data.features);
            data.features->preorder_kinds.push_back(kind_name);
            ++data.features->kind_freq[kind_name];
        }
    }

    bool opened_scope = false;
    bool opened_function = false;
    if (data.normalization != nullptr && opens_scope(kind)) {
        push_scope(*data.normalization);
        opened_scope = true;
        if (kind == CXCursor_FunctionDecl) {
            push_function_counters(*data.normalization);
            opened_function = true;
        }
    }

    auto node = make_node(cursor, data.parent, data.depth);
    if (data.normalization != nullptr) {
        normalize_node_value(kind, *node, *data.normalization);
    }
    AstNode* current = node.get();

    if (data.parent != nullptr) {
        data.parent->children.push_back(std::move(node));
    }

    traverse_data child_data;
    child_data.parent = current;
    child_data.features = data.features;
    child_data.normalization = data.normalization;
    child_data.depth = data.depth + 1;

    clang_visitChildren(cursor, for_kids, &child_data);

    if (data.normalization != nullptr && opened_scope) {
        if (opened_function) {
            pop_function_counters(*data.normalization);
        }
        pop_scope(*data.normalization);
    }
}

struct parsed_unit {
    CXIndex index = nullptr;
    CXTranslationUnit translation_unit = nullptr;
};

static parsed_unit parse_code_to_unit(const std::string& code) {
    parsed_unit parsed;

    parsed.index = clang_createIndex(0, 0);
    const char* file_name = "input.cpp";

    CXUnsavedFile unsaved_file{};
    unsaved_file.Filename = file_name;
    unsaved_file.Contents = code.c_str();
    unsaved_file.Length = static_cast<unsigned long>(code.size());

    const char* args[] = {
        "-x", "c++",
        "-std=c++20"
    };

    CXErrorCode error_code = clang_parseTranslationUnit2(
        parsed.index,
        file_name,
        args, 3,
        &unsaved_file, 1,
        CXTranslationUnit_None,
        &parsed.translation_unit
    );

    if (error_code != CXError_Success || parsed.translation_unit == nullptr) {
        if (parsed.translation_unit != nullptr) {
            clang_disposeTranslationUnit(parsed.translation_unit);
            parsed.translation_unit = nullptr;
        }
        clang_disposeIndex(parsed.index);
        parsed.index = nullptr;
    }

    return parsed;
}

AstFeatures analyze_ast(const std::string& code) {
    AstFeatures features;

    parsed_unit parsed = parse_code_to_unit(code);
    if (parsed.translation_unit == nullptr) {
        return features;
    }

    features.parse_ok = true;

    CXCursor root_cursor = clang_getTranslationUnitCursor(parsed.translation_unit);

    AstNode scratch_root;
    normalization_state normalization;
    traverse_data data;
    data.parent = &scratch_root;
    data.features = &features;
    data.normalization = &normalization;
    data.depth = 0;
    dfs_collect(root_cursor, data);

    clang_disposeTranslationUnit(parsed.translation_unit);
    clang_disposeIndex(parsed.index);

    return features;
}

AstTree build_ast_tree(const std::string& code) {
    AstTree tree;

    parsed_unit parsed = parse_code_to_unit(code);
    if (parsed.translation_unit == nullptr) {
        return tree;
    }

    tree.parse_ok = true;

    CXCursor root_cursor = clang_getTranslationUnitCursor(parsed.translation_unit);
    tree.root = make_node(root_cursor, nullptr, 0);

    traverse_data child_data;
    child_data.parent = tree.root.get();
    child_data.features = nullptr;
    normalization_state normalization;
    child_data.normalization = &normalization;
    child_data.depth = 1;
    clang_visitChildren(root_cursor, for_kids, &child_data);

    fill_subtree_size(tree.root.get());

    clang_disposeTranslationUnit(parsed.translation_unit);
    clang_disposeIndex(parsed.index);

    return tree;
}

std::pair<AstFeatures, AstTree> analyze_and_build_ast(const std::string& code) {
    AstFeatures features;
    AstTree tree;

    parsed_unit parsed = parse_code_to_unit(code);
    if (parsed.translation_unit == nullptr) {
        return {features, std::move(tree)};
    }

    features.parse_ok = true;
    tree.parse_ok = true;

    CXCursor root_cursor = clang_getTranslationUnitCursor(parsed.translation_unit);
    tree.root = make_node(root_cursor, nullptr, 0);

    traverse_data child_data;
    child_data.parent = tree.root.get();
    child_data.features = &features;
    normalization_state normalization;
    child_data.normalization = &normalization;
    child_data.depth = 1;
    
    clang_visitChildren(root_cursor, for_kids, &child_data);

    fill_subtree_size(tree.root.get());

    clang_disposeTranslationUnit(parsed.translation_unit);
    clang_disposeIndex(parsed.index);

    return {features, std::move(tree)};
}
