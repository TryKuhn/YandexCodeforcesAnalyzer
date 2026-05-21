#pragma once

#include <string>
#include <unordered_map>

/// @brief Expands type aliases and strips boilerplate in C++ source code.
///
/// Removes `using namespace X;` directives (ubiquitous boilerplate) and
/// expands `typedef TYPE ALIAS`, `using NAME = TYPE`, and `#define NAME BODY`
/// (non-function-like) aliases: definition lines are consumed and all uses
/// of each alias name are replaced by its fully-expanded body. Function-like
/// macros (`#define F(...)`) are silently discarded; they should be handled
/// upstream by `PreprocessCode` (g++ -E).
///
/// @param code C++ source after comment removal and preprocessing.
/// @return Source text with alias definitions removed and alias names expanded.
std::string ExpandAliases(const std::string& code);

/// @brief Collects value-macro, typedef, and C++11 alias-declaration definitions.
///
/// Phase 1 of the expansion pipeline. Lines that define an alias are consumed
/// (not forwarded to the output). `using namespace X;` directives are also
/// stripped (boilerplate). Function-like macros (`#define NAME(...)`) are
/// silently discarded.
///
/// @param code Source text with comments already removed.
/// @param alias_map Output map populated with `{name -> raw body}` entries.
/// @return Source text with all alias-definition and namespace-using lines stripped out.
std::string CollectAliases(const std::string& code,
                           std::unordered_map<std::string, std::string>& alias_map);

/// @brief Transitively expands alias bodies within the alias map itself.
///
/// Phase 2 of the expansion pipeline. Runs up to `max_passes` substitution
/// rounds on the map values so that chained aliases such as
/// `ll -> long long` / `vll -> vector<ll>` resolve to `vector<long long>`.
///
/// @param alias_map Map of `{name -> body}` to expand in-place.
/// @param max_passes Maximum number of substitution passes. [1, 10]
void TransitivelyExpandAliasMap(std::unordered_map<std::string, std::string>& alias_map,
                                int max_passes = 5);

/// @brief Replaces alias names in source text with their expanded bodies.
///
/// Phase 3 of the expansion pipeline. Performs whole-word substitution:
/// a match is only replaced when it is not adjacent to an identifier character
/// (`[A-Za-z0-9_]`). Occurrences inside double-quoted string literals are skipped.
///
/// @param code Source text with alias-definition lines already removed.
/// @param alias_map Fully-expanded map of `{name -> body}`.
/// @return Source text with all alias names replaced by their expansions.
std::string ApplyAliasMap(const std::string& code,
                          const std::unordered_map<std::string, std::string>& alias_map);
