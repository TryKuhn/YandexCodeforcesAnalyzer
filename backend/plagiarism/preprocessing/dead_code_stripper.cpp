#include "dead_code_stripper.h"

#include <algorithm>
#include <set>
#include <string>
#include <vector>

#include <clang-c/Index.h>

struct SrcRange {
    int start_line;
    int end_line;
    bool operator<(const SrcRange& o) const { return start_line < o.start_line; }
};

static bool IsFromMainFile(CXCursor c) {
    return clang_Location_isFromMainFile(clang_getCursorLocation(c)) != 0;
}

static SrcRange GetRange(CXCursor c) {
    unsigned s = 0, e = 0;
    CXSourceRange r = clang_getCursorExtent(c);
    clang_getSpellingLocation(clang_getRangeStart(r), nullptr, &s, nullptr, nullptr);
    clang_getSpellingLocation(clang_getRangeEnd(r), nullptr, &e, nullptr, nullptr);
    return {static_cast<int>(s), static_cast<int>(e)};
}

// ── Pass 1: collect the USR of every declaration that is actually referenced ──

static CXChildVisitResult CollectRefsVisitor(CXCursor c, CXCursor, CXClientData data) {
    auto* refs = static_cast<std::set<std::string>*>(data);
    if (!IsFromMainFile(c)) return CXChildVisit_Continue;

    if (clang_getCursorKind(c) == CXCursor_DeclRefExpr) {
        CXCursor decl = clang_getCursorReferenced(c);
        if (!clang_Cursor_isNull(decl)) {
            CXString usr = clang_getCursorUSR(decl);
            const char* s = clang_getCString(usr);
            if (s && *s) refs->insert(s);
            clang_disposeString(usr);
        }
    }
    return CXChildVisit_Recurse;
}

// ── Pass 2: identify dead AST nodes ──────────────────────────────────────────

static bool IsEmptyCompound(CXCursor c) {
    if (clang_getCursorKind(c) != CXCursor_CompoundStmt) return false;
    int count = 0;
    clang_visitChildren(c,
        +[](CXCursor, CXCursor, CXClientData d) -> CXChildVisitResult {
            ++(*static_cast<int*>(d));
            return CXChildVisit_Break;
        },
        &count);
    return count == 0;
}

struct CollectDeadCtx {
    std::vector<SrcRange> dead_ranges;
    const std::set<std::string>* referenced_usrs;
};

static CXChildVisitResult CollectDeadVisitor(CXCursor c, CXCursor, CXClientData data) {
    auto* ctx = static_cast<CollectDeadCtx*>(data);
    if (!IsFromMainFile(c)) return CXChildVisit_Continue;

    CXCursorKind kind = clang_getCursorKind(c);

    // ── Empty for / while / do loops ─────────────────────────────────────────
    if (kind == CXCursor_ForStmt || kind == CXCursor_WhileStmt || kind == CXCursor_DoStmt) {
        // Grab the last child of this statement — that is the loop body.
        CXCursor body = clang_getNullCursor();
        clang_visitChildren(c,
            +[](CXCursor child, CXCursor, CXClientData d) -> CXChildVisitResult {
                *static_cast<CXCursor*>(d) = child;
                return CXChildVisit_Continue;
            },
            &body);

        if (!clang_Cursor_isNull(body) && IsEmptyCompound(body)) {
            ctx->dead_ranges.push_back(GetRange(c));
            return CXChildVisit_Continue;  // skip children of the dead loop
        }
    }

    // ── Unreferenced local VarDecl ────────────────────────────────────────────
    // Only strip function-scope locals; leave globals, struct members, params alone.
    if (kind == CXCursor_VarDecl) {
        CXCursorKind parent_kind =
            clang_getCursorKind(clang_getCursorSemanticParent(c));

        if (parent_kind == CXCursor_FunctionDecl) {
            CXString usr_cx = clang_getCursorUSR(c);
            const char* usr = clang_getCString(usr_cx);
            bool referenced = usr && *usr &&
                              ctx->referenced_usrs->count(std::string(usr)) > 0;
            clang_disposeString(usr_cx);

            if (!referenced) {
                ctx->dead_ranges.push_back(GetRange(c));
                return CXChildVisit_Continue;
            }
        }
    }

    return CXChildVisit_Recurse;
}

// ── Erase the collected line ranges from the source text ─────────────────────

static std::string EraseLineRanges(const std::string& code,
                                   std::vector<SrcRange>& ranges) {
    if (ranges.empty()) return code;

    std::sort(ranges.begin(), ranges.end());

    // Merge overlapping / adjacent ranges
    std::vector<SrcRange> merged;
    for (auto& r : ranges) {
        if (!merged.empty() && r.start_line <= merged.back().end_line) {
            merged.back().end_line = std::max(merged.back().end_line, r.end_line);
        } else {
            merged.push_back(r);
        }
    }

    std::string result;
    result.reserve(code.size());
    int line = 1;
    std::size_t mi = 0;

    for (char ch : code) {
        bool dead = mi < merged.size() &&
                    line >= merged[mi].start_line &&
                    line <= merged[mi].end_line;

        if (!dead) result += ch;

        if (ch == '\n') {
            ++line;
            while (mi < merged.size() && line > merged[mi].end_line) ++mi;
        }
    }

    return result;
}

// ── Public entry point ───────────────────────────────────────────────────────

std::string StripDeadCode(const std::string& code) {
    if (code.empty()) return code;

    CXIndex index = clang_createIndex(0, 0);

    CXUnsavedFile unsaved{};
    unsaved.Filename = "input.cpp";
    unsaved.Contents = code.c_str();
    unsaved.Length   = static_cast<unsigned long>(code.size());

    const char* args[] = { "-x", "c++", "-std=c++20" };

    CXTranslationUnit tu = nullptr;
    CXErrorCode err = clang_parseTranslationUnit2(
        index, "input.cpp",
        args, 3,
        &unsaved, 1,
        CXTranslationUnit_None,
        &tu);

    if (err != CXError_Success || !tu) {
        clang_disposeIndex(index);
        return code;  // graceful fallback: leave code unchanged
    }

    CXCursor root = clang_getTranslationUnitCursor(tu);

    // Pass 1: collect referenced USRs
    std::set<std::string> referenced_usrs;
    clang_visitChildren(root, CollectRefsVisitor, &referenced_usrs);

    // Pass 2: collect dead ranges
    CollectDeadCtx ctx;
    ctx.referenced_usrs = &referenced_usrs;
    clang_visitChildren(root, CollectDeadVisitor, &ctx);

    clang_disposeTranslationUnit(tu);
    clang_disposeIndex(index);

    return EraseLineRanges(code, ctx.dead_ranges);
}
