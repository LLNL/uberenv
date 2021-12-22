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


def cmake_cache_entry(name, value, vtype=None):
    """
    Helper that creates CMake cache entry strings used in
    'host-config' files.
    """
    if vtype is None:
        if value == "ON" or value == "OFF":
            vtype = "BOOL"
        else:
            vtype = "PATH"
    return 'set({0} "{1}" CACHE {2} "")\n\n'.format(name, value, vtype)


class Magictestlib(Package):
    """Magictestlib"""

    homepage = "http://example.com/"
    url      = "http://example.com/"
    git      = "http://example.com/"

    version('1.0.0', 'c8b277080a00041cfc4f64619e31f6d6',preferred=True)

    depends_on('zlib')

    ###################################
    # build phases used by this package
    ###################################
    phases = ['hostconfig']

    def url_for_version(self, version):
        dummy_tar_path =  os.path.abspath(pjoin(os.path.split(__file__)[0]))
        dummy_tar_path = pjoin(dummy_tar_path,"magictestlib.tar.gz")
        url      = "file://" + dummy_tar_path
        return url


    def _get_host_config_path(self, spec):
        sys_type = spec.architecture
        # if on llnl systems, we can use the SYS_TYPE
        if "SYS_TYPE" in env:
            sys_type = env["SYS_TYPE"]
        host_config_path = "{0}-{1}-{2}-magictestlib-{3}.cmake".format(socket.gethostname(),
                                                                  sys_type,
                                                                  spec.compiler,
                                                                  spec.dag_hash())
        dest_dir = spec.prefix
        host_config_path = os.path.abspath(join_path(dest_dir,
                                                     host_config_path))
        return host_config_path

    def hostconfig(self, spec, prefix):
        """
        This method creates a mock 'host-config' file.
        """
        if not os.path.isdir(spec.prefix):
            os.mkdir(spec.prefix)

        #######################
        # Compiler Info
        #######################
        c_compiler = env["SPACK_CC"]
        cpp_compiler = env["SPACK_CXX"]

        #######################################################################
        # Directly fetch the names of the actual compilers to create a
        # 'host config' file that works outside of the spack install env.
        #######################################################################
        # get hostconfig name
        host_cfg_fname = self._get_host_config_path(spec)

        cfg = open(host_cfg_fname, "w")
        cfg.write("##################################\n")
        cfg.write("# spack generated host-config\n")
        cfg.write("##################################\n")
        #######################
        # Spack Compiler info
        #######################
        cfg.write("#######\n")
        cfg.write("# using %s compiler spec\n" % spec.compiler)
        cfg.write("#######\n\n")
        cfg.write("# c compiler used by spack\n")
        cfg.write(cmake_cache_entry("CMAKE_C_COMPILER", c_compiler))
        cfg.write("# cpp compiler used by spack\n")
        cfg.write(cmake_cache_entry("CMAKE_CXX_COMPILER", cpp_compiler))

        ######
        # ZLIB
        cfg.write(cmake_cache_entry("ZLIB_DIR", spec['zlib'].prefix))

        #######################
        # Finish host-config
        #######################
        cfg.write("##################################\n")
        cfg.write("# end spack generated host-config\n")
        cfg.write("##################################\n")
        cfg.close()

        host_cfg_fname = os.path.abspath(host_cfg_fname)
        tty.info("spack generated host-config file: " + host_cfg_fname)

