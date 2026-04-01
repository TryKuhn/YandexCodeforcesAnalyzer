#include "tokenizer.h"
#include <clang-c/Index.h>

#include <string>
#include <vector>

static std::string ConvertCxStringToStdString(CXString s) {
    const char* cstr = clang_getCString(s);
    std::string result = cstr ? cstr : "";
    clang_disposeString(s);
    return result;
}

static TokenType ConvertClangTokenKindToTokenType(CXTokenKind kind) {
    switch (kind) {
        case CXToken_Punctuation:
            return TokenType::Punctuation;
        case CXToken_Keyword:
            return TokenType::Keyword;
        case CXToken_Identifier:
            return TokenType::Identifier;
        case CXToken_Literal:
            return TokenType::Literal;
        default:
            return TokenType::Unknown;
    }
}

static std::size_t GetTokenStartOffset(CXTranslationUnit tu, CXToken token) {
    CXSourceLocation location = clang_getTokenLocation(tu, token);

    unsigned offset = 0;
    clang_getSpellingLocation(location, nullptr, nullptr, nullptr, &offset);

    return static_cast<std::size_t>(offset);
}

std::vector<Token> TokenizerWithClang(const std::string& code) {
    std::vector<Token> result;

    CXIndex index = clang_createIndex(0, 0);

    const char* filename = "input.cpp";

    CXUnsavedFile unsaved;
    unsaved.Filename = filename;
    unsaved.Contents = code.c_str();
    unsaved.Length = code.size();

    const char* args[] = {
        "-x", "c++",
        "-std=c++20"
    };

    CXTranslationUnit tu = nullptr;
    CXErrorCode err = clang_parseTranslationUnit2(
        index,
        filename,
        args, 3,
        &unsaved, 1,
        CXTranslationUnit_None,
        &tu
    );

    if (err != CXError_Success || tu == nullptr) {
        clang_disposeIndex(index);
        return result;
    }

    CXFile file = clang_getFile(tu, filename);
    if (file == nullptr) {
        clang_disposeTranslationUnit(tu);
        clang_disposeIndex(index);
        return result;
    }

    CXSourceLocation start = clang_getLocationForOffset(tu, file, 0);
    CXSourceLocation end =
        clang_getLocationForOffset(tu, file, static_cast<unsigned>(code.size()));

    CXSourceRange range = clang_getRange(start, end);

    CXToken* tokens = nullptr;
    unsigned numTokens = 0;
    clang_tokenize(tu, range, &tokens, &numTokens);

    result.reserve(numTokens);

    for (unsigned i = 0; i < numTokens; ++i) {
        Token token;
        token.type = ConvertClangTokenKindToTokenType(clang_getTokenKind(tokens[i]));
        token.text = ConvertCxStringToStdString(clang_getTokenSpelling(tu, tokens[i]));
        token.offset = GetTokenStartOffset(tu, tokens[i]);
        result.push_back(token);
    }

    clang_disposeTokens(tu, tokens, numTokens);
    clang_disposeTranslationUnit(tu);
    clang_disposeIndex(index);

    return result;
}