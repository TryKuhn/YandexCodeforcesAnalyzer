#pragma once

#include <string>
#include <cstddef>

std::size_t CalculateLevenshteinDistance(const std::string& left,
                                         const std::string& right);

double CalculateLevenshteinSimilarity(const std::string& left,
                                      const std::string& right);