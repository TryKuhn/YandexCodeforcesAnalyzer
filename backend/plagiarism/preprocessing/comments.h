#pragma once

#include <string>

class DeleteComments {
public:
    DeleteComments(const std::string& code);
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

    // функции для обработки различных состояний
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

    // флаг показывает, правда ли, что у нас сейчас символ вида \"
    // и наш текущий символ надо трактовать как часть литерала

    bool flag_ = false;


};
std::string RemoveComments(const std::string& code);