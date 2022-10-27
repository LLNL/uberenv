#! /bin/sh

# Called by linux.yaml to install required dependencies for linux tests

sudo apt-get update
sudo apt-get install binutils \
                    gcc \
                    g++ \
                    gfortran \
                    cmake \
                    python3 \
                    perl \
                    git \
                    git-lfs \
                    curl \
                    wget \
                    tar \
                    unzip \
                    build-essential
