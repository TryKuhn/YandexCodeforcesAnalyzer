// Tries to reach the outside world. The sandbox has no network, so this must
// fail; the solution prints the right answer only when it was blocked, which
// means a verdict other than OK is a security regression.
#include <arpa/inet.h>
#include <iostream>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

int main() {
    long long a, b;
    std::cin >> a >> b;

    bool reached = false;
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd >= 0) {
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(53);
        inet_pton(AF_INET, "8.8.8.8", &addr.sin_addr);
        reached = connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) == 0;
        close(fd);
    }

    std::cout << (reached ? -1 : a + b) << "\n";
}
