#!/bin/bash

set -euxo pipefail

SOURCE_DIR="/deps/hailort-src"
BUILD_DIR="/tmp/hailort-mps-build"

apt-get update
apt-get install -y --no-install-recommends \
    libssl-dev \
    zlib1g-dev

cmake \
    -S "$SOURCE_DIR" \
    -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DHAILO_BUILD_SERVICE=ON \
    -DHAILO_BUILD_UT=OFF \
    -DHAILO_BUILD_EXAMPLES=OFF

cmake --build "$BUILD_DIR" \
    --parallel 2

cmake --install "$BUILD_DIR"

ldconfig

mkdir -p /rootfs/usr/local/lib

cp -a \
    /usr/local/lib/libhailort.so* \
    /rootfs/usr/local/lib/

cd "$SOURCE_DIR/hailort/libhailort/bindings/python/platform"

python3 setup.py bdist_wheel \
    --dist-dir /wheels
