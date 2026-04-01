#include "normalize.h"

#include "cpp_preprocessor.h"
#include "comments.h"
#include "line_endings.h"
#include "lines.h"

std::string NormalizerForTokenizer(const std::string& code) {
    std::string result = NormalizeLineEndings(code);
    result = RemoveComments(result);
    result = NormalizeLines(result);
    result = PreprocessCode(result);
    return result;
}

std::string NormalizerForAST(const std::string& code) {
    std::string result = NormalizeLineEndings(code);
    result = RemoveComments(result);
    return result;
}