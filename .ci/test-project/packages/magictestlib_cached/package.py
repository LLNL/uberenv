# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import glob
import os
import shutil
import socket
from os import environ as env

import llnl.util.tty as tty

from spack import *

def get_spec_path(spec, package_name, path_replacements={}, use_bin=False):
    """Extracts the prefix path for the given spack package
       path_replacements is a dictionary with string replacements for the path.
    """

    if not use_bin:
        path = spec[package_name].prefix
    else:
        path = spec[package_name].prefix.bin

    path = os.path.realpath(path)

    for key in path_replacements:
        path = path.replace(key, path_replacements[key])

    return path


class MagictestlibCached(CachedCMakePackage):
    """MagictestlibCached"""

    homepage = "http://example.com/"
    url      = "http://example.com/"
    git      = "http://example.com/"

    version('1.0.0', 'c8b277080a00041cfc4f64619e31f6d6',preferred=True)

    depends_on('zlib')
    depends_on('hdf5~mpi')

    def url_for_version(self, version):
        dummy_tar_path = os.path.abspath(os.path.join(os.path.split(__file__)[0]))
        dummy_tar_path = os.path.join(dummy_tar_path, "magictestlib_cached.tar.gz")
        url = "file://" + dummy_tar_path
        return url

    def _get_sys_type(self, spec):
        sys_type = spec.architecture
        # if on llnl systems, we can use the SYS_TYPE
        if "SYS_TYPE" in env:
            sys_type = env["SYS_TYPE"]
        return sys_type

    @property
    def cache_name(self):
        hostname = socket.gethostname()
        if "SYS_TYPE" in env:
            # Are we on a LLNL system then strip node number
            hostname = hostname.rstrip('1234567890')
        return "{0}-{1}-{2}@{3}.cmake".format(
            hostname,
            self._get_sys_type(self.spec),
            self.spec.compiler.name,
            self.spec.compiler.version
        )

    def initconfig_package_entries(self):
        spec = self.spec
        entries = []

        # TPL locations
        entries.append("#------------------{0}".format("-" * 60))
        entries.append("# TPLs")
        entries.append("#------------------{0}\n".format("-" * 60))

        path_replacements = {}

        # Try to find the common prefix of the TPL directory, including the
        # compiler. If found, we will use this in the TPL paths
        compiler_str = str(spec.compiler).replace('@','-')
        prefix_paths = prefix.split(compiler_str)
        tpl_root = ""
        if len(prefix_paths) == 2:
            tpl_root = os.path.join( prefix_paths[0], compiler_str )
            path_replacements[tpl_root] = "${TPL_ROOT}"
            entries.append(cmake_cache_path("TPL_ROOT", tpl_root))

        # required tpls
        for dep in ('hdf5', 'zlib'):
            dep_dir = get_spec_path(spec, dep, path_replacements)
            entries.append(cmake_cache_path('%s_DIR' % dep.upper(),
                                            dep_dir))

        return entries
