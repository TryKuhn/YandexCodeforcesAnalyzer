#pragma once

#include <string>
#include <vector>

class LinesNormalizer {
public:
    explicit LinesNormalizer(const std::string& code);
    std::string Transform();

private:
    void SplitLines();
    void NormalizeEachLine();
    void RemoveEmptyLines();
    void JoinLines();
    void RemoveIncludesAndPragmas();

    bool IsEmptyLine(const std::string& line) const;

    std::string code_;
    std::vector<std::string> lines_;
};

std::string NormalizeLines(const std::string& code);