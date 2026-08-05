#include "testlib.h"

int main(int argc, char* argv[]) {
    registerTestlibCmd(argc, argv);
    long long jury = ans.readLong();
    long long participant = ouf.readLong();
    if (jury != participant)
        quitf(_wa, "expected %lld, found %lld", jury, participant);
    quitf(_ok, "answer is %lld", jury);
}
