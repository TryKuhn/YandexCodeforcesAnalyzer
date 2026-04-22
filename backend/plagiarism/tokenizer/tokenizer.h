#pragma once

#include <string>
#include <vector>
#include "../models/token.h"

std::vector<Token> TokenizerWithClang(const std::string& code);