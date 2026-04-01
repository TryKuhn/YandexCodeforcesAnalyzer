#pragma once

#include <string>

class StringNormalizer {
public:
    explicit StringNormalizer(const std::string& line);
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

std::string NormalizeString(const std::string& line);