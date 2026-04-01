#include "levenshtein_similarity.h"

#include <algorithm>
#include <vector>

std::size_t CalculateLevenshteinDistance(const std::string& left,
                                         const std::string& right) {
    if (left.empty()) {
        return right.size();
    }

    if (right.empty()) {
        return left.size();
    }

    std::vector<std::size_t> previous(right.size() + 1);
    std::vector<std::size_t> current(right.size() + 1);

    for (std::size_t j = 0; j <= right.size(); ++j) {
        previous[j] = j;
    }

    for (std::size_t i = 1; i <= left.size(); ++i) {
        current[0] = i;

        for (std::size_t j = 1; j <= right.size(); ++j) {
            std::size_t cost = (left[i - 1] == right[j - 1]) ? 0 : 1;

            current[j] = std::min({
                                          previous[j] + 1,
                                          current[j - 1] + 1,
                                          previous[j - 1] + cost
                                  });
        }

        std::swap(previous, current);
    }

    return previous[right.size()];
}

double CalculateLevenshteinSimilarity(const std::string& left,
                                      const std::string& right) {
    std::size_t max_length = std::max(left.size(), right.size());

    if (max_length == 0) {
        return 1.0;
    }

    std::size_t distance = CalculateLevenshteinDistance(left, right);

    return 1.0 - static_cast<double>(distance) / static_cast<double>(max_length);
}