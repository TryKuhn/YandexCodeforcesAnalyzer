#pragma once

#include <string>

/// @brief Removes dead code patterns that are commonly inserted to confuse
///        plagiarism detectors.
///
/// Uses Clang to parse the code and detect two classes of dead code:
///
/// 1. **Empty loops** — `for`, `while`, or `do` statements whose body is an
///    empty compound statement `{}`. These produce no observable effect and are
///    trivially added as noise.
///
/// 2. **Unreferenced local variables** — `VarDecl` nodes that are never
///    mentioned in any `DeclRefExpr` within the same translation unit.
///    Only function-scope locals are considered; globals and parameters are
///    left untouched.
///
/// Returns the original code unchanged on Clang parse failure, so callers
/// can proceed with normalization even for ill-formed input.
///
/// @param code C++ source text (after comment removal and line normalization).
/// @return Source text with dead code statements removed.
std::string StripDeadCode(const std::string& code);
