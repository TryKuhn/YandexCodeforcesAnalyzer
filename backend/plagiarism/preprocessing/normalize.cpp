#include "normalize.h"

#include "cpp_preprocessor.h"
#include "comments.h"
#include "line_endings.h"
#include "lines.h"

std::string NormalizeCode(const std::string& code) {
    std::string result = NormalizeLineEndings(code);
    result = RemoveComments(result);
    result = NormalizeLines(result);
    result = PreprocessCode(result);
    return result;
}