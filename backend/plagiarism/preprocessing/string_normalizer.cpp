
#include "string_normalizer.h"

StringNormalizer::StringNormalizer(const std::string& line) : line_(line) {}

void StringNormalizer::RemoveLeadingAndTrailingSpaces() {
    std::size_t left = 0;
    while (left < line_.size() && (line_[left] == ' ' || line_[left] == '\t')) {
        left++;
    }
    std::size_t right = line_.size();
    while (right > left && (line_[right - 1] == ' ' || line_[right - 1] == '\t')) {
        --right;
    }

    line_ = line_.substr(left, right - left);
}

void StringNormalizer::ProcessNormal() {
    if (line_[i_] == '"') {
        now_ = State::StringLiteral;
        result_ += line_[i_];
        flag_ = false;
    } else if (line_[i_] == '\'') {
        now_ = State::CharLiteral;
        result_ += line_[i_];
        flag_ = false;
    } else if (line_[i_] == ' ' || line_[i_] == '\t') {
        if (result_.empty() || result_.back() != ' ') {
            result_ += ' ';
        }
    } else {
        result_ += line_[i_];
    }
}

void StringNormalizer::ProcessStringLiteral() {
    result_ += line_[i_];
    if (flag_) {
        flag_ = false;
    } else if (line_[i_] == '\\') {
        flag_ = true;
    } else if (line_[i_] == '\'') {
        now_ = State::Normal;
    }
}

void StringNormalizer::ProcessCharLiteral() {
    char c = line_[i_];
    result_ += c;

    if (flag_) {
        flag_ = false;
    } else if (c == '\\') {
        flag_ = true;
    } else if (c == '\'') {
        now_ = State::Normal;
    }
}

void StringNormalizer::RemoveDoubleSpaces() {
    for (i_ = 0; i_ < line_.size(); ++i_) {
        if (now_ == State::Normal) {
            ProcessNormal();
        } else if (now_ == State::CharLiteral) {
            ProcessCharLiteral();
        } else if (now_ == State::Normal) {
            ProcessNormal();
        }
    }
    line_ = result_;
}

std::string StringNormalizer::Transform() {
    RemoveLeadingAndTrailingSpaces();
    RemoveDoubleSpaces();
    return line_;
}

std::string NormalizeString(const std::string& line) {
    return StringNormalizer(line).Transform();
}