#pragma once

#include <string>

/// @brief Removes C and C++ comments from source code.
///
/// Handles `//` line comments, `/* */` block comments, and correctly skips
/// comment-like sequences inside string and character literals.
class DeleteComments {
public:
    /// @brief Constructs the processor over the given source text.
    /// @param code Raw C++ source code.
    explicit DeleteComments(const std::string& code);

    /// @brief Runs the comment-removal pass.
    /// @return Source text with all comment content replaced by nothing.
    std::string Process();

private:
    enum class State {
        Normal,
        Slash,
        LineComment,
        BlockComment,
        StringLiteral,
        CharLiteral
    };

    void ProcessNormal();
    void ProcessSlash();
    void ProcessLineComment();
    void ProcessBlockComment();
    void ProcessStringLiteral();
    void ProcessCharLiteral();

    const std::string& code_;
    std::string result_;
    std::size_t i_ = 0;
    State now_ = State::Normal;

    // True when the previous character was a backslash inside a literal,
    // meaning the current character must be treated as an escape sequence body.
    bool flag_ = false;
};

/// @brief Convenience wrapper: constructs a DeleteComments and calls Process().
/// @param code Raw C++ source code.
/// @return Source text with all comment content removed.
std::string RemoveComments(const std::string& code);