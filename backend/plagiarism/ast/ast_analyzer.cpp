#include "ast_analyzer.h"

#include <clang-c/Index.h>

#include <algorithm>
#include <string>

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

struct traverse_data {
    AstFeatures* features = nullptr;
    int depth = 0;
};

static void dfs(CXCursor cursor, AstFeatures& features, int depth);

static enum CXChildVisitResult for_kids(
    CXCursor cursor,
    CXCursor parent,
    CXClientData client_data
) {
    (void)parent;

    auto* data = static_cast<traverse_data*>(client_data);
    dfs(cursor, *data->features, data->depth);

    return CXChildVisit_Continue;
}

static void dfs(CXCursor cursor, AstFeatures& features, int depth) {
    CXCursorKind kind = clang_getCursorKind(cursor);

    if (kind != CXCursor_TranslationUnit && !is_from_main_file(cursor)) {
        return;
    }

    features.max_depth = std::max(features.max_depth, depth);

    if (is_interesting_kind(kind)) {
        std::string kind_name = get_kind_name(cursor);

        count_interesting_kind(kind, features);
        features.preorder_kinds.push_back(kind_name);
        ++features.kind_freq[kind_name];
    }

    traverse_data child_data;
    child_data.features = &features;
    child_data.depth = depth + 1;

    clang_visitChildren(cursor, for_kids, &child_data);
}

AstFeatures analyze_ast(const std::string& code) {
    AstFeatures features;

    CXIndex index = clang_createIndex(0, 0);

    const char* file_name = "input.cpp";

    CXUnsavedFile unsaved_file;
    unsaved_file.Filename = file_name;
    unsaved_file.Contents = code.c_str();
    unsaved_file.Length = static_cast<unsigned long>(code.size());

    const char* args[] = {
        "-x", "c++",
        "-std=c++20"
    };

    CXTranslationUnit translation_unit = nullptr;
    CXErrorCode error_code = clang_parseTranslationUnit2(
        index,
        file_name,
        args, 3,
        &unsaved_file, 1,
        CXTranslationUnit_None,
        &translation_unit
    );

    if (error_code != CXError_Success || translation_unit == nullptr) {
        clang_disposeIndex(index);
        return features;
    }

    features.parse_ok = true;

    CXCursor root_cursor = clang_getTranslationUnitCursor(translation_unit);
    dfs(root_cursor, features, 0);

    clang_disposeTranslationUnit(translation_unit);
    clang_disposeIndex(index);

    return features;
}