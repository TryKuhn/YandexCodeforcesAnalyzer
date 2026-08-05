#include <iostream>

// right idea, unreadable output: the checker cannot parse a number here
int main() {
    long long a, b;
    std::cin >> a >> b;
    std::cout << "the answer is " << a + b << "\n";
}
