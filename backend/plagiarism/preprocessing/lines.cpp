#include "lines.h"
#include "string_normalizer.h"

LinesNormalizer::LinesNormalizer(const std::string& code)
    : code_(code) {
}

bool LinesNormalizer::IsEmptyLine(const std::string& line) const {
    return line.empty();
}

void LinesNormalizer::SplitLines() {
    std::string current;

    for (char c : code_) {
        if (c == '\n') {
            lines_.push_back(current);
            current = "";
        } else {
            current += c;
        }
    }
    lines_.push_back(current);
}

void LinesNormalizer::NormalizeEachLine() {
    for (std::string& line : lines_) {
        line = NormalizeString(line);
    }
}
void LinesNormalizer::JoinLines() {
    code_ = "";
    for (std::string& line : lines_) {
         code_ += line;
         code_ += '\n';
    }
}

void LinesNormalizer::RemoveEmptyLines() {
    std::vector < std::string > result;
    for (std::string& line : lines_) {
        if (!IsEmptyLine(line)) {
            result.push_back(line);
        }
    }
    lines_ = result;
}
void LinesNormalizer::RemoveIncludesAndPragmas() {
    std::vector < std::string > result;
    for (std::string& line : lines_) {
        if (!(line.size() >= 8 && line.substr(0, 8) == "#include") &&
            !(line.size() >= 7 && line.substr(0, 7) == "#pragma")) {
            result.push_back(line);
        }
    }
    lines_ = result;
}
std::string LinesNormalizer::Transform() {
    SplitLines();
    NormalizeEachLine();
    RemoveEmptyLines();
    RemoveIncludesAndPragmas();
    JoinLines();
    return code_;
};

std::string NormalizeLines(const std::string& code) {
    return LinesNormalizer(code).Transform();
}