// Tries to exhaust the host by forking without limit.
// The process cap must stop it: either fork fails and the program dies (RE),
// or it spins on failing forks until the clock runs out (TLE).
#include <iostream>
#include <unistd.h>

int main() {
    long long a, b;
    std::cin >> a >> b;
    while (true) {
        fork();
    }
    std::cout << a + b << "\n";
}
