#pragma once

#include <string>

/// @brief Converts all line endings to Unix `\n`.
///
/// Replaces `\r\n` (Windows) and standalone `\r` (old Mac) with `\n`
/// so that subsequent passes can assume a single consistent line separator.
///
/// @param code Raw source text with any line-ending style.
/// @return Source text where every line ending is `\n`.
std::string NormalizeLineEndings(const std::string& code);