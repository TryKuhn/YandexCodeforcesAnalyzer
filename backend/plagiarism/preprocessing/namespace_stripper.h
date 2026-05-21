#pragma once

#include <string>

/// @brief Strips namespace and scope qualifiers from qualified names.
///
/// Collapses `A::B::C` to `C` throughout the source text. This normalizes
/// `std::vector` and `vector`, `std::sort` and `sort`, etc., so that code
/// using explicit `std::` prefixes compares identically to code that relies
/// on `using namespace std;`.
///
/// Qualifiers are only stripped when both sides of `::` are identifier tokens.
/// Occurrences inside string and character literals are left untouched.
/// A leading `::` (global-namespace qualifier) is also stripped.
///
/// @param code C++ source text (after preprocessing and alias expansion).
/// @return Source text with all namespace/scope qualifiers removed.
std::string StripNamespaceQualifiers(const std::string& code);
