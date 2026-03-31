#include "line_endings.h"

#include <string>

std::string NormalizeLineEndings(const std::string& code) {
    std::string result;

    for(std::size_t i = 0; i < code.size(); i++) {
        if (code[i] == '\r') {
            if ((i != code.size() - 1 && code[i + 1] == '\n')) {
                continue;
            }
            result.push_back('\n');
        } else {
            result.push_back(code[i]);
        }
    }
    return result;
}