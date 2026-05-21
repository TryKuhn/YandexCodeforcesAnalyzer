#pragma once

#include <string>
#include <vector>

/// @brief Applies line-level normalization passes to C++ source text.
///
/// Normalization consists of splitting into lines, trimming/collapsing
/// whitespace within each line, removing empty lines, and stripping
/// `#include`, `#pragma`, `#undef`, and `#line` directives. `#define`
/// lines are intentionally kept so that the downstream `PreprocessCode`
/// (g++ -E) can expand them.
class LinesNormalizer {
public:
    /// @brief Constructs the normalizer over the given source text.
    /// @param code Source text with comments already removed.
    explicit LinesNormalizer(const std::string& code);

    /// @brief Runs all normalization passes and returns the result.
    /// @return Normalized source text with directives and empty lines removed.
    std::string Transform();

private:
    void SplitLines();
    void NormalizeEachLine();
    void RemoveEmptyLines();
    void JoinLines();
    void RemoveDirectives();

    bool IsEmptyLine(const std::string& line) const;

    std::string code_;
    std::vector<std::string> lines_;
};

/// @brief Convenience wrapper: constructs a LinesNormalizer and calls Transform().
/// @param code Source text with comments already removed.
/// @return Normalized source text with directives and empty lines removed.
std::string NormalizeLines(const std::string& code);