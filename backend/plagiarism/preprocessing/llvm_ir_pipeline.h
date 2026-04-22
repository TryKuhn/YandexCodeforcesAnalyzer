#pragma once

#include <string>

// Generates optimized LLVM IR (.ll text) from C++ source code.
// Returns empty string on any tooling or IO error.
std::string BuildLlvmIrFromCode(const std::string& code);

