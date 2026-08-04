#include <iostream>

// honest TLE: real work that cannot finish in time, no sleeps or asserts
int main() {
    long long a, b;
    std::cin >> a >> b;
    volatile long long sum = 0;
    for (long long i = 1;; ++i) {
        sum += i % 7;
        if (i == 0) break;
    }
    std::cout << a + b + sum << "\n";
}
