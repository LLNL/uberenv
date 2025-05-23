.. ############################################################################
.. # Copyright (c) 2014-2025, Lawrence Livermore National Security, LLC.
.. #
.. # Produced at the Lawrence Livermore National Laboratory
.. #
.. # LLNL-CODE-666778
.. #
.. # All rights reserved.
.. #
.. # This file is part of Conduit.
.. #
.. # For details, see: http://software.llnl.gov/conduit/.
.. #
.. # Please also read conduit/LICENSE
.. #
.. # Redistribution and use in source and binary forms, with or without
.. # modification, are permitted provided that the following conditions are met:
.. #
.. # * Redistributions of source code must retain the above copyright notice,
.. #   this list of conditions and the disclaimer below.
.. #
.. # * Redistributions in binary form must reproduce the above copyright notice,
.. #   this list of conditions and the disclaimer (as noted below) in the
.. #   documentation and/or other materials provided with the distribution.
.. #
.. # * Neither the name of the LLNS/LLNL nor the names of its contributors may
.. #   be used to endorse or promote products derived from this software without
.. #   specific prior written permission.
.. #
.. # THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
.. # AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
.. # IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
.. # ARE DISCLAIMED. IN NO EVENT SHALL LAWRENCE LIVERMORE NATIONAL SECURITY,
.. # LLC, THE U.S. DEPARTMENT OF ENERGY OR CONTRIBUTORS BE LIABLE FOR ANY
.. # DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
.. # DAMAGES  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
.. # OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
.. # HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
.. # STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
.. # IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
.. # POSSIBILITY OF SUCH DAMAGE.
.. #
.. ############################################################################

.. _building_with_uberenv:

Uberenv
~~~~~~~

**Uberenv** automates using a package manager to build and deploy software.
It uses `Spack <http://www.spack.io>`_ on Unix-based systems (e.g. Linux and macOS)
and `Vcpkg <https://github.com/microsoft/vcpkg>`_ on Windows systems.

Many projects leverage package managers, like Spack and Vcpkg, to help build the software dependencies needed to
develop and deploy their projects on HPC systems. Uberenv is a python script that helps automate the usage of a package manager to build
third-party dependencies for development and deployment.

Uberenv was released as part of Conduit (https://github.com/LLNL/conduit/). It is included in-source in several projects. The
https://github.com/llnl/uberenv/ repo is used to hold the latest reference version of Uberenv.

Several projects are using Uberenv for Continuous Integration (CI) purposes. The process is documented `here <https://radiuss-ci.readthedocs.io/en/latest/index.html>`_.

uberenv.py
~~~~~~~~~~

Uberenv is a single file python script (``uberenv.py``) that automates fetching Spack or Vcpkg, building and installing third party dependencies,
and can optionally install top-level packages as well. To automate the full install process, Uberenv uses a target Spack or Vcpkg
package along with extra settings such as compilers and external third party package details for common HPC platforms.

Uberenv is included directly in a project's source code repo, usually in the folder: ``scripts/uberenv/``.
This folder is also used to store extra configuration files unique to the target project.
Uberenv uses a ``project.json`` file to specify project details, including the target package name
and the base branch or commit in the package manager.

Conduit's source repo serves as an example for Uberenv and Spack configuration files, etc:

https://github.com/LLNL/conduit/tree/master/scripts/uberenv

Uberenv can also be used as a submodule of the user project, where one must provide a configuration file named
``.uberenv_config.json`` in a parent directory. This file is similar to ``project.json`` in purpose, but should
additionally provide the entries ``spack_configs_path`` and ``spack_packages_path``.
See :ref:`project_configuration` for more details.

.. Note::
   Uberenv requires python 3.3 or above.

Uberenv is developed by LLNL, originally in support of the `Ascent <https://github.com/alpine-dav/ascent/>`_,
`Axom <https://github.com/llnl/axom>`_, and `Conduit <https://github.com/llnl/conduit>`_  projects. It is now also used
by `Umpire <https://github.com/llnl/umpire>`_, `CHAI <https://github.com/llnl/CHAI>`_, `RAJA <https://github.com/llnl/RAJA>`_
and `Serac <https://github.com/llnl/serac>`_, among others.


Command Line Options
~~~~~~~~~~~~~~~~~~~~

Build Configuration
-------------------

Uberenv has a few options that allow you to control how dependencies are built:

 =========================== ============================================== =================================================
  Option                      Description                                    Default
 =========================== ============================================== =================================================
  ``--prefix``                Destination directory                          ``uberenv_libs``
  ``--spec``                  Spack spec without preceding package name      linux: **%gcc**
                                                                             osx: **%clang**
  ``--spack-env-name``        The name of the created Spack Environment       ``spack_env``
  ``--spack-env-file``        Path to Spack Environment config               See :ref:`spack_configs`
                              (e.g. spack.yaml)
  ``--spack-build-mode``      Mode used to build third party dependencies    ``dev-build``
  ``--spack-debug``           Enable Spack debug mode for all commands       **none** (False)
  ``-k``                      Ignore SSL Errors                              **False**
  ``--install``               Fully install target, not just dependencies    **False**
  ``--run_tests``             Invoke tests during build and against install  **False**
  ``--setup-only``            Only download and setup Spack                  **False**
  ``--skip-setup``            Only install (using pre-setup Spack)           **False**
  ``--setup-and-env-only``    Download, setup Spack, and generate env file   **False**
  ``--skip-setup-and-env``    Only install (using pre-setup Spack/env file)  **False**
  ``--spack-externals``       Space delimited string of packages for         **none**
                              Spack to search for externals
  ``--spack-compiler-paths``  Space delimited string of paths for            **none**
                              Spack to search for compilers
  ``--project-json``          File for project specific settings             See :ref:`project_configuration`
  ``--triplet``               (vcpkg) Target architecture and linkage        ``VCPKG_DEFAULT_TRIPLET`` environment variable,
                                                                             if present, ``x86-Windows`` otherwise
 =========================== ============================================== =================================================

The ``--spack-env-name`` will be created in path specified by ``--prefix``.

The ``-k`` option exists for sites where SSL certificate interception undermines fetching
from github and https hosted source tarballs. When enabled, Uberenv clones Spack using:

``git -c http.sslVerify=false clone https://github.com/llnl/spack.git``

And passes ``-k`` to any Spack commands that may fetch via https.


Default invocations:

**Linux**

``python scripts/uberenv/uberenv.py --prefix uberenv_libs --spec %gcc``

**OSX**

``python scripts/uberenv/uberenv.py --prefix uberenv_libs --spec %clang``

**Windows**

``python scripts/uberenv/uberenv.py --prefix uberenv_libs --triplet x86-windows``

See `Vcpkg user docs <https://vcpkg.readthedocs.io/en/latest/users/triplets/>`_ for more information about triplets.

Use the ``--install`` option to install the target package (not just its development dependencies):

``python scripts/uberenv/uberenv.py --install``


If the target Spack package supports Spack's testing hooks, you can run tests during the build process to validate the build and install, using the ``--run_tests`` option:

``python scripts/uberenv/uberenv.py --install --run_tests``

For details on Spack's spec syntax, see the `Spack Specs & dependencies <https://spack.readthedocs.io/en/latest/basic_usage.html#specs-dependencies>`_ documentation.

.. _spack_configs:

Spack Configurations
--------------------

Uberenv looks for the ``spack.yaml`` configuration file, also known as an Environment file, under ``scripts/uberenv/spack_configs/{platform}`` or
``{spack_config_paths}/{platform}``, where: ``{platform}`` must match the platform determined by Uberenv (``SYS_TYPE`` on LC and ``darwin`` on
OSX). ``{spack_configs_path}`` can be specified in the json config file.

You may instead use the ``--spack-env-file`` option to enforce the use of a specific Spack Environment file. This file
does not need to be called ``spack.yaml`` if you wish to call it something else, like according to its platform for
example. See the `Spack Environments (spack.yaml) <https://spack.readthedocs.io/en/latest/environments.html>`_
documentation for details.

If an Environment file cannot be found, Uberenv will generate one and copy it to ``{package_source_dir}/spack.yaml``.
Spack will find packages and compilers on its own based on ``--spack-externals`` and ``--spack-compiler-paths``. If
these options are not specified either on the command line or project json, Spack will find all compilers and packages
it can. To prevent Uberenv from creating an Environment file in future builds, specify your ``--spack-environment-file``
to the one generated.

When run, ``uberenv.py`` check outs a specific version of Spack from github as ``spack`` in the
destination directory. It then uses Spack to build and install the target packages' dependencies into
``spack/opt/spack/``. Finally, the target package generates a host-config file ``{hostname}.cmake``, which is
copied to destination directory. This file specifies the compiler settings and paths to all of the dependencies.

.. note::
    Instead of two yaml files (``packages.yaml`` and ``compilers.yaml``), Ubernev uses a single ``spack.yaml``, which is
    simply the combination of the original two under ``spack:``.

    .. code-block:: yaml

        spack:
            # contents of packages.yaml
            # contents of compilers.yaml

.. _project_configuration:

Project Configuration
---------------------

Project level configuration options can also be addressed using a json file and some settings can be overridden on command line.  This json file
is found in the in the following order:

1. ``--project-json=[path/to/project.json]`` command line option
2. ``project.json`` that lives in the same directory as ``uberenv.py``
3. ``.uberenv_config.json`` found recursively in a parent directory (typically at the root of your project)

Project settings are as follows:

 ========================= ========================== ================================================ =======================================
  Setting                  Command line Option        Description                                      Default
 ========================= ========================== ================================================ =======================================
  package_name             ``--package-name``         Spack package name                               **None**
  package_version          **None**                   Spack package version                            **None**
  package_final_phase      ``--package-final-phase``  Controls after which phase Spack should stop     **None**
  package_source_dir       ``--package-source-dir``   Controls the source directory Spack should use   **None**
  force_commandline_prefix **None**                   Force user to specify `--prefix` on command line ``false``
  spack_url                **None**                   Download url for Spack                           ``https://github.com/spack/spack.git``
  spack_commit             **None**                   Spack commit to checkout                         **None**
  spack_activate           **None**                   Spack packages to activate                       **None**
  spack_build_mode         ``--spack-build-mode``     Set mode used to build TPLs with Spack           ``dev-build``
  spack_configs_path       **None**                   Directory with Spack configs to be autodetected  ``spack_configs``
  spack_packages_path      **None**                   Directory|List with Package Repos to be added    ``packages``
  spack_setup_clingo       **None**                   Do not install clingo if set to ``false``        **None**
  spack_externals          ``--spack-externals``      Space delimited string of packages for Spack to  **None**
                                                      search for externals
  spack_compiler_paths     ``--spack-compiler-paths`` Space delimited string of paths for Spack to     **None**
                                                      search for compilers
  vcpkg_url                **None**                   Download url for Vcpkg                           ``https://github.com/microsoft/vcpkg``
  vcpkg_branch             **None**                   Vcpkg branch to checkout                         ``master``
  vcpkg_commit             **None**                   Vcpkg commit to checkout                         **None**
  vcpkg_ports_path         ``--vcpkg-ports-path``     Folder with vcpkg ports files                    **None**
 ========================= ========================== ================================================ =======================================

If a ``spack_commit`` is present, it supercedes the ``spack_branch`` option, and similarly for ``vcpkg_commit``and ``vcpkg_branch``.

When used as a submodule ``.uberenv_config.json`` should define both ``spack_configs_path`` and ``spack_packages_path``,
providing Uberenv with the respective location of ``spack_configs`` and ``packages`` directories.
Note that they cannot sit next to ``uberenv.py``, since by default, the Uberenv repo does not provide them.

``spack_packages_path`` can either be a singular directory or a list of directories. These are relative to the
location of the ``.uberenv_config.json``. When it is a list, the directories are added from left to right in Spack
and right-most directories have the highest priority. The built-in Spack package repository is the lowest priority.
Example:

.. code-block:: json

    "spack_packages_path": "package/repo/higher/than/spacks",
    "spack_packages_path": ["package/repo/higher/than/spacks", "package/repo/even/higher"],

.. note::
    Uberenv no longer copies all directories that exist under ``spack_packages_path`` to the cloned
    Spack. A ``repo.yaml`` is now required in the previous directory of each packages path instead.
    Inside ``repo.yaml``, you only need a namespace, which can simply be the name of the package
    you're installing. See
    `Spack's documentation <https://spack.readthedocs.io/en/latest/repositories.html#namespaces>`_.

.. note::
    For an example of how to craft a ``project.json`` / ``.uberenv_config.json`` file a target project,
    see: `Axom's project.json file <https://github.com/LLNL/axom/tree/develop/scripts/uberenv/project.json>`_.

Optimization
------------

Uberenv also features options to optimize the installation

 ===================== ============================================== ================================================
  Option               Description                                    Default
 ===================== ============================================== ================================================
  ``--mirror``         Location of a Spack mirror                     **None**
  ``--create-mirror``  Creates a Spack mirror at specified location   **None**
  ``--upstream``       Location of a Spack upstream                   **None**
 ===================== ============================================== ================================================

.. note::
    These options are only currently available for spack.
