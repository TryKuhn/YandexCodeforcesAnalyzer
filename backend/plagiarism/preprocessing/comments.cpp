#include "comments.h"

DeleteComments::DeleteComments(const std::string& code)
        : code_(code) {
}

void DeleteComments::ProcessNormal() {
    if (code_[i_] == '"') {
        result_ += code_[i_];
        now_ = State::StringLiteral;
        flag_ = false;
    } else if (code_[i_] == '/') {
        now_ = State::Slash;
    } else if (code_[i_] == '\'') {
        result_ += code_[i_];
        now_ = State::CharLiteral;
        flag_ = false;
    } else {
        result_ += code_[i_];
    }
}

void DeleteComments::ProcessSlash() {
    if (code_[i_] == '/') {
        now_ = State::LineComment;
    } else if (code_[i_] == '*') {
        now_ = State::BlockComment;
    } else {
        result_ += '/';
        result_ += code_[i_];
        now_ = State::Normal;
    }
}

void DeleteComments::ProcessBlockComment() {
    if (code_[i_] == '*' && (i_ != code_.size() - 1 && code_[i_ + 1] == '/')) {
        i_++;
        now_ = State::Normal;
    }
}
void DeleteComments::ProcessLineComment() {
    if (code_[i_] == '\n') {
        now_ = State::Normal;
    }
}
void DeleteComments::ProcessStringLiteral() {
    result_ += code_[i_];

    if (flag_) {
        flag_ = false;
    } else if (code_[i_] == '\\') {
        flag_ = true;
    } else if (code_[i_] == '"') {
        now_ = State::Normal;
    }
}

void DeleteComments::ProcessCharLiteral() {
    result_ += code_[i_];

    if (flag_) {
        flag_ = false;
    } else if (code_[i_] == '\\') {
        flag_ = true;
    } else if (code_[i_] == '\'') {
        now_ = State::Normal;
    }
}

std::string DeleteComments::Process() {
    for (i_ = 0; i_ < code_.size(); ++i_) {
        if (now_ == State::Normal) {
            ProcessNormal();
        } else if (now_ == State::Slash) {
            ProcessSlash();
        } else if (now_ == State::LineComment) {
            ProcessLineComment();
        } else if (now_ == State::BlockComment) {
            ProcessBlockComment();
        } else if (now_ == State::StringLiteral) {
            ProcessStringLiteral();
        } else if (now_ == State::CharLiteral) {
            ProcessCharLiteral();
        }
    }

    if (now_ == State::Slash) {
        result_ += '/';
    }
    return result_;
}

std::string RemoveComments(const std::string& code) {
    return DeleteComments(code).Process();
}