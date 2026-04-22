#pragma once

#include <string>
#include <vector>

#include "../models/token.h"

Token NormalizeToken(const Token& token);
std::vector<Token> NormalizeTokens(const std::vector<Token>& tokens);

std::vector<std::string> TextTokens(const std::vector<Token>& tokens);