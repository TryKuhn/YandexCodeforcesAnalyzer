#pragma once

#include <string>

/// @brief Normalizes whitespace in a single line of C++ source.
///
/// Collapses consecutive spaces/tabs to one space, removes leading and
/// trailing whitespace, and preserves the content of string and character
/// literals unchanged.
class StringNormalizer {
public:
    /// @brief Constructs the normalizer over a single source line.
    /// @param line One line of C++ source (no newline).
    explicit StringNormalizer(const std::string& line);

    /// @brief Runs whitespace normalization.
    /// @return Normalized line with collapsed and trimmed whitespace.
    std::string Transform();

private:
    enum class State {
        Normal,
        StringLiteral,
        CharLiteral
    };

    void ProcessNormal();
    void ProcessStringLiteral();
    void ProcessCharLiteral();

    void RemoveLeadingAndTrailingSpaces();
    void RemoveDoubleSpaces();

    std::string line_;

    State now_ = State::Normal;
    std::size_t i_ = 0;
    std::string result_;
    bool flag_ = false;
};

/// @brief Convenience wrapper: constructs a StringNormalizer and calls Transform().
/// @param line One line of C++ source (no newline).
/// @return Normalized line with collapsed and trimmed whitespace.
std::string NormalizeString(const std::string& line);