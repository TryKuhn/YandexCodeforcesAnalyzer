// Same idea as the fork bomb, but through threads: isolate counts tasks, not
// just processes, so the cap must catch this too.
#include <iostream>
#include <pthread.h>

static void* spin(void*) {
    while (true) {
    }
    return nullptr;
}

int main() {
    long long a, b;
    std::cin >> a >> b;
    while (true) {
        pthread_t thread;
        pthread_create(&thread, nullptr, spin, nullptr);
    }
    std::cout << a + b << "\n";
}
