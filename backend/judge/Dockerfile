# build context is ./backend, so judge shares testlib.h with the backend
# isolate is built from source so the version is pinned, not whatever apt ships
FROM ubuntu:24.04 AS isolate-build

ARG ISOLATE_VERSION=v2.6

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        pkg-config \
        libcap-dev \
        libseccomp-dev \
        libsystemd-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch ${ISOLATE_VERSION} https://github.com/ioi/isolate.git /src
WORKDIR /src
RUN make isolate isolate-cg-keeper


FROM ubuntu:24.04

# g++ and python3 are the languages we judge, the rest is what isolate links against
RUN apt-get update && apt-get install -y --no-install-recommends \
        g++ \
        python3 \
        libcap2 \
        libseccomp2 \
        libsystemd0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=isolate-build /src/isolate /usr/local/bin/isolate
COPY --from=isolate-build /src/isolate-cg-keeper /usr/local/bin/isolate-cg-keeper
COPY --from=isolate-build /src/default.cf /usr/local/etc/isolate

# isolate manages namespaces and cgroups, which needs the setuid bit
RUN chmod 4755 /usr/local/bin/isolate

# the same testlib the backend ships to Polygon, on the default include path
COPY api/user/polygon/archive/assets/testlib.h /usr/local/include/testlib.h

WORKDIR /app
COPY judge/requirements-dev.txt ./
COPY judge/pytest.ini ./
COPY judge/app ./app
COPY judge/tests ./tests

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

CMD ["python3", "-c", "print('judge service: no entrypoint yet, see YCA-403')"]
