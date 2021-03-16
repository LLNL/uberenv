# uberenv
Automates using a package manager to build and deploy software.

[![Read the Docs](https://readthedocs.org/projects/uberenv/badge/?version=latest)](https://uberenv.readthedocs.io)

Uberenv is a python script that helps automate building
third-party dependencies for development and deployment. 

Uberenv uses Spack (https://www.spack.io/) on Unix-based systems (e.g. Linux and macOS)
and Vcpkg (https://github.com/microsoft/vcpkg) on Windows systems.

Uberenv was released as part of the Conduit project (https://github.com/LLNL/conduit/). 
It is included in-source in several projects, this repo is used to hold the latest reference version.

For more details, see Uberenv's documention:

https://uberenv.readthedocs.io

You can also find details about how it is used in Conduit's documentation:

https://llnl-conduit.readthedocs.io/en/latest/building.html#building-conduit-and-third-party-dependencies

Conduit's source repo also serves as an example for uberenv and spack configuration files, etc:

https://github.com/LLNL/conduit/tree/master/scripts/uberenv
