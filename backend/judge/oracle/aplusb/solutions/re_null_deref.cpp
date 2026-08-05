#include <iostream>

// honest RE: a real null dereference, not abort() or assert(false)
int main() {
    long long a, b;
    std::cin >> a >> b;
    long long* broken = nullptr;
    std::cout << a + b + *broken << "\n";
}
