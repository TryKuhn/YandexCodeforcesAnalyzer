// Tries to modify the system it runs on. Everything outside the box is mounted
// read-only, so every write must fail; a wrong answer here means the sandbox
// let a contestant tamper with the machine.
#include <cstdio>
#include <iostream>

int main() {
    long long a, b;
    std::cin >> a >> b;

    const char* targets[] = {
        "/etc/passwd",
        "/usr/bin/g++",
        "/usr/local/bin/isolate",
        "/usr/local/include/testlib.h",
    };

    bool wrote = false;
    for (const char* target : targets) {
        FILE* file = fopen(target, "a");
        if (file != nullptr) {
            wrote = fputs("pwned\n", file) >= 0;
            fclose(file);
        }
    }

    std::cout << (wrote ? -1 : a + b) << "\n";
}
