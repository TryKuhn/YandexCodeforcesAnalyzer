#include "normalize.h"

#include "alias_expander.h"
#include "comments.h"
#include "cpp_preprocessor.h"
#include "line_endings.h"
#include "lines.h"
#include "namespace_stripper.h"

std::string NormalizeForTokenizer(const std::string& code) {
    std::string result = NormalizeLineEndings(code);
    result = RemoveComments(result);
    result = NormalizeLines(result);
    result = PreprocessCode(result);
    result = ExpandAliases(result);
    result = StripNamespaceQualifiers(result);
    result = NormalizeLines(result);
    return result;
}

std::string NormalizeForAST(const std::string& code) {
    std::string result = NormalizeLineEndings(code);
    result = RemoveComments(result);
    result = NormalizeLines(result);
    result = PreprocessCode(result);
    result = ExpandAliases(result);
    result = StripNamespaceQualifiers(result);
    result = NormalizeLines(result);
    return result;
}