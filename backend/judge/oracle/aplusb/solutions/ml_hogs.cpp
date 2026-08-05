#include <iostream>
#include <vector>

// honest MLE: really touches the memory it allocates, so it cannot be optimised away
int main() {
    long long a, b;
    std::cin >> a >> b;
    std::vector<std::vector<long long>> hog;
    while (true) {
        hog.emplace_back(1 << 20, a + b);
        hog.back()[0] = hog.size();
    }
}
