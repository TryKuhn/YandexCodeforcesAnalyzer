#include "alias_expander.h"

#include <algorithm>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

static bool IsIdentChar(char c) {
    return (c >= 'a' && c <= 'z') ||
           (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') ||
           c == '_';
}

// Returns true if `name` appears at position `pos` in `text` as a whole word
// (not preceded or followed by an identifier character).
static bool IsWholeWordAt(const std::string& text, std::size_t pos, std::size_t len) {
    if (pos > 0 && IsIdentChar(text[pos - 1])) {
        return false;
    }
    if (pos + len < text.size() && IsIdentChar(text[pos + len])) {
        return false;
    }
    return true;
}

static std::string TrimWhitespace(const std::string& s) {
    std::size_t start = s.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) {
        return {};
    }
    std::size_t end = s.find_last_not_of(" \t\r\n");
    return s.substr(start, end - start + 1);
}

std::string CollectAliases(const std::string& code,
                           std::unordered_map<std::string, std::string>& alias_map) {
    std::istringstream stream(code);
    std::string line;
    std::string output;
    output.reserve(code.size());

    while (std::getline(stream, line)) {
        std::string trimmed = TrimWhitespace(line);

        // --- #define NAME BODY (value macro only, no parenthesis after name) ---
        if (trimmed.size() >= 8 && trimmed.substr(0, 7) == "#define" && !IsIdentChar(trimmed[7])) {
            std::string rest = TrimWhitespace(trimmed.substr(7));

            // Extract the macro name (sequence of identifier chars)
            std::size_t name_end = 0;
            while (name_end < rest.size() && IsIdentChar(rest[name_end])) {
                ++name_end;
            }

            if (name_end > 0) {
                std::string name = rest.substr(0, name_end);
                std::string after_name = rest.substr(name_end);

                // Function-like macro: next char is '(' — drop the line without recording
                if (!after_name.empty() && after_name[0] == '(') {
                    // Silently discard function-like macros
                    continue;
                }

                std::string body = TrimWhitespace(after_name);
                alias_map[name] = body;
                continue;
            }
        }

        // --- typedef TYPE ALIAS; (skip function-pointer typedefs containing '(') ---
        if (trimmed.size() >= 8 && trimmed.substr(0, 7) == "typedef" && !IsIdentChar(trimmed[7])) {
            std::string rest = TrimWhitespace(trimmed.substr(7));

            // Skip function-pointer typedefs
            if (rest.find('(') != std::string::npos) {
                output += line;
                output += '\n';
                continue;
            }

            // Remove trailing semicolon
            if (!rest.empty() && rest.back() == ';') {
                rest.pop_back();
                rest = TrimWhitespace(rest);
            }

            // The alias name is the last whitespace-separated token
            std::size_t last_space = rest.find_last_of(" \t");
            if (last_space != std::string::npos) {
                std::string alias = TrimWhitespace(rest.substr(last_space + 1));
                std::string type  = TrimWhitespace(rest.substr(0, last_space));

                if (!alias.empty() && !type.empty() && IsIdentChar(alias[0])) {
                    // Verify the whole alias is an identifier
                    bool valid = true;
                    for (char c : alias) {
                        if (!IsIdentChar(c)) { valid = false; break; }
                    }
                    if (valid) {
                        alias_map[alias] = type;
                        continue;
                    }
                }
            }
        }

        // --- using NAME = TYPE; (strip `using namespace ...`) ---
        if (trimmed.size() >= 6 && trimmed.substr(0, 5) == "using" && !IsIdentChar(trimmed[5])) {
            std::string rest = TrimWhitespace(trimmed.substr(5));

            // `using namespace ...` — strip: ubiquitous boilerplate, not algorithm logic
            if (rest.size() >= 9 && rest.substr(0, 9) == "namespace") {
                continue;
            }

            std::size_t eq = rest.find('=');
            if (eq != std::string::npos) {
                std::string name = TrimWhitespace(rest.substr(0, eq));
                std::string type_part = TrimWhitespace(rest.substr(eq + 1));

                // Remove trailing semicolon
                if (!type_part.empty() && type_part.back() == ';') {
                    type_part.pop_back();
                    type_part = TrimWhitespace(type_part);
                }

                // Validate name is a plain identifier
                bool valid = !name.empty();
                for (char c : name) {
                    if (!IsIdentChar(c)) { valid = false; break; }
                }

                if (valid && !type_part.empty()) {
                    alias_map[name] = type_part;
                    continue;
                }
            }
        }

        output += line;
        output += '\n';
    }

    return output;
}

void TransitivelyExpandAliasMap(std::unordered_map<std::string, std::string>& alias_map,
                                int max_passes) {
    for (int pass = 0; pass < max_passes; ++pass) {
        bool changed = false;

        for (auto& [name, body] : alias_map) {
            // Apply every other alias to this body
            for (const auto& [other_name, other_body] : alias_map) {
                if (other_name == name || other_name.empty() || other_body.empty()) {
                    continue;
                }

                std::string expanded;
                expanded.reserve(body.size());
                std::size_t pos = 0;
                std::size_t nlen = other_name.size();

                while (pos < body.size()) {
                    std::size_t found = body.find(other_name, pos);
                    if (found == std::string::npos) {
                        expanded.append(body, pos, body.size() - pos);
                        break;
                    }

                    if (IsWholeWordAt(body, found, nlen)) {
                        expanded.append(body, pos, found - pos);
                        expanded.append(other_body);
                        pos = found + nlen;
                        changed = true;
                    } else {
                        expanded.append(body, pos, found - pos + 1);
                        pos = found + 1;
                    }
                }

                body = std::move(expanded);
            }
        }

        if (!changed) {
            break;
        }
    }
}

std::string ApplyAliasMap(const std::string& code,
                          const std::unordered_map<std::string, std::string>& alias_map) {
    if (alias_map.empty()) {
        return code;
    }

    // Collect alias names sorted longest-first to avoid partial replacements
    std::vector<std::string> names;
    names.reserve(alias_map.size());
    for (const auto& [name, _] : alias_map) {
        if (!name.empty()) {
            names.push_back(name);
        }
    }
    std::sort(names.begin(), names.end(),
              [](const std::string& a, const std::string& b) {
                  return a.size() > b.size();
              });

    std::string result;
    result.reserve(code.size());

    bool in_string = false;
    bool escape_next = false;
    std::size_t i = 0;
    const std::size_t n = code.size();

    while (i < n) {
        char c = code[i];

        // Track double-quoted string literals to skip replacements inside them
        if (!in_string) {
            if (c == '"') {
                in_string = true;
                escape_next = false;
                result += c;
                ++i;
                continue;
            }

            // Try to match any alias name starting at position i
            bool matched = false;
            if (IsIdentChar(c)) {
                for (const auto& name : names) {
                    std::size_t nlen = name.size();
                    if (i + nlen > n) {
                        continue;
                    }
                    if (code.compare(i, nlen, name) == 0 && IsWholeWordAt(code, i, nlen)) {
                        const auto& body = alias_map.at(name);
                        result.append(body);
                        i += nlen;
                        matched = true;
                        break;
                    }
                }
            }

            if (!matched) {
                result += c;
                ++i;
            }
        } else {
            // Inside a string literal — copy verbatim, track escape sequences
            result += c;
            if (escape_next) {
                escape_next = false;
            } else if (c == '\\') {
                escape_next = true;
            } else if (c == '"') {
                in_string = false;
            }
            ++i;
        }
    }

    return result;
}

std::string ExpandAliases(const std::string& code) {
    std::unordered_map<std::string, std::string> alias_map;

    std::string stripped = CollectAliases(code, alias_map);
    TransitivelyExpandAliasMap(alias_map);
    return ApplyAliasMap(stripped, alias_map);
}
