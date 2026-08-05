// Usage: generator <max-abs-value> <seed>
#include "testlib.h"

int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);
    long long limit = atoll(argv[1]);
    println(rnd.next(-limit, limit), rnd.next(-limit, limit));
}
