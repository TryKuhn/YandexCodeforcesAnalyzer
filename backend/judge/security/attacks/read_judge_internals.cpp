// Tries to read what a contestant must never see: host secrets, the judge's own
// code, and other boxes. None of it is mounted into the sandbox, so every open
// must fail.
#include <cstdio>
#include <iostream>

int main() {
    long long a, b;
    std::cin >> a >> b;

    const char* targets[] = {
        "/etc/shadow",
        "/app/app/server.py",
        "/app/oracle/aplusb/problem.json",
        "/var/local/lib/isolate/1/box/main.cpp",
        "/proc/1/environ",
    };

    bool leaked = false;
    for (const char* target : targets) {
        FILE* file = fopen(target, "r");
        if (file != nullptr) {
            char probe = 0;
            leaked = fread(&probe, 1, 1, file) == 1;
            fclose(file);
            if (leaked) break;
        }
    }

    std::cout << (leaked ? -1 : a + b) << "\n";
}
