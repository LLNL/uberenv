#! /bin/sh
# Temporary file, NOT meant to be run. Just a reference on what works.
# TODO test uberenv-pkg option

# NOTES:
# spack develop:
#  - does not have a -u final_phase option
#  - used before install command to say "hey we are developing this package and here is its location"
#  - need to concretize after this command
#  - do `spack find dev_path=*` to test if worked properly
#
# spack install:
#  - no need for --no-add, since that is default behavior
#

# General setup
source ~/.profile
cd .ci/test-project
s1 ../../uberenv.py --project-json=dev_build_config.json --spack-config-dir=../../../uberenv_spack_configs/toss_3_x86_64_ib --setup-only
source uberenv_libs/spack/share/spack/setup-env.sh

# Create and setup spack env
spack env create -d spack_env <spack-config-dir>
spack env activate spack_env
spack add magictestlib_cached@1.0.0%gcc #magictestlib for uberenv_pkg

# For develop builds ONLY
cp packages/magictestlib.tar.gz . && tar -xvf magictestlib.tar.gz
spack develop --no-clone --path=../src magictestlib_cached@1.0.0%gcc

# Install for EVERY build mode
spack concretize --force --fresh
spack install magictestlib_cached@1.0.0%gcc
