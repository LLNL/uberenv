#!/bin/sh
"exec" "python" "-u" "-B" "$0" "$@"
###############################################################################
# Copyright (c) 2014-2021, Lawrence Livermore National Security, LLC.
#
# Produced at the Lawrence Livermore National Laboratory
#
# LLNL-CODE-666778
#
# All rights reserved.
#
# This file is part of Conduit.
#
# For details, see https://lc.llnl.gov/conduit/.
#
# Please also read conduit/LICENSE
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the disclaimer below.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the disclaimer (as noted below) in the
#   documentation and/or other materials provided with the distribution.
#
# * Neither the name of the LLNS/LLNL nor the names of its contributors may
#   be used to endorse or promote products derived from this software without
#   specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL LAWRENCE LIVERMORE NATIONAL SECURITY,
# LLC, THE U.S. DEPARTMENT OF ENERGY OR CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
###############################################################################

"""
 file: uberenv.py

 description: automates using a package manager to install a project.
 Uses spack on Unix-based systems and Vcpkg on Windows-based systems.

"""

import os
import sys
import stat
import subprocess
import shutil
import socket
import platform
import json
import datetime
import glob
import re

from optparse import OptionParser

from os import environ as env
from os.path import join as pjoin
from os.path import abspath as pabs


def sexe(cmd,ret_output=False,echo=False):
    """ Helper for executing shell commands. """
    if echo:
        print("[exe: {0}]".format(cmd))
    if ret_output:
        p = subprocess.Popen(cmd,
                             shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        out = p.communicate()[0]
        out = out.decode('utf8')
        return p.returncode,out
    else:
        return subprocess.call(cmd,shell=True)


def parse_args():
    "Parses args from command line"
    parser = OptionParser()
    parser.add_option("--install",
                      action="store_true",
                      dest="install",
                      default=False,
                      help="Install `package_name`, not just its dependencies.")

    # where to install
    parser.add_option("--prefix",
                      dest="prefix",
                      default=None,
                      help="destination directory")

    # what compiler to use
    parser.add_option("--spec",
                      dest="spec",
                      default=None,
                      help="spack compiler spec")

    # for vcpkg, what architecture to target
    parser.add_option("--triplet",
                      dest="vcpkg_triplet",
                      default=None,
                      help="vcpkg architecture triplet")

    # optional location of spack mirror
    parser.add_option("--mirror",
                      dest="mirror",
                      default=None,
                      help="spack mirror directory")

    # flag to create mirror
    parser.add_option("--create-mirror",
                      action="store_true",
                      dest="create_mirror",
                      default=False,
                      help="Create spack mirror")

    # optional location of spack upstream
    parser.add_option("--upstream",
                      dest="upstream",
                      default=None,
                      help="add an external spack instance as upstream")

    # this option allows a user to explicitly to select a
    # group of spack settings files (compilers.yaml , packages.yaml)
    parser.add_option("--spack-config-dir",
                      dest="spack_config_dir",
                      default=None,
                      help="dir with spack settings files (spack.yaml, config.yaml, compilers.yaml, packages.yaml, etc)")

    # this option allows a user to set the directory for their vcpkg ports on Windows
    parser.add_option("--vcpkg-ports-path",
                      dest="vcpkg_ports_path",
                      default=None,
                      help="dir with vckpkg ports")

    # overrides package_name
    parser.add_option("--package-name",
                      dest="package_name",
                      default=None,
                      help="override the default package name")

    # uberenv spack tpl build mode
    parser.add_option("--spack-build-mode",
                      dest="spack_build_mode",
                      default=None,
                      help="set mode used to build third party dependencies with spack"
                           "(options: 'dev-build' 'uberenv-pkg' 'install' "
                           "[default: 'dev-build'] )\n")

    # controls after which package phase spack should stop
    parser.add_option("--package-final-phase",
                      dest="package_final_phase",
                      default=None,
                      help="override the default phase after which spack should stop")

    # controls source_dir spack should use to build the package
    parser.add_option("--package-source-dir",
                      dest="package_source_dir",
                      default=None,
                      help="override the default source dir spack should use")

    # a file that holds settings for a specific project
    # using uberenv.py
    parser.add_option("--project-json",
                      dest="project_json",
                      default=pjoin(uberenv_script_dir(),"project.json"),
                      help="uberenv project settings json file")

    # option to explicitly set the number of build jobs
    parser.add_option("-j",
                      dest="build_jobs",
                      default=None,
                      help="Explicitly set build jobs")

    # flag to use insecure curl + git
    parser.add_option("-k",
                      action="store_true",
                      dest="ignore_ssl_errors",
                      default=False,
                      help="Ignore SSL Errors")

    # option to force a pull of the package manager
    parser.add_option("--pull",
                      action="store_true",
                      dest="repo_pull",
                      default=False,
                      help="Pull from package manager, if repo already exists")

    # option to force for clean of packages specified to
    # be cleaned in the project.json
    parser.add_option("--clean",
                      action="store_true",
                      dest="spack_clean",
                      default=False,
                      help="Force uninstall of packages specified in project.json")

    # option to tell spack to run tests
    parser.add_option("--run_tests",
                      action="store_true",
                      dest="run_tests",
                      default=False,
                      help="Invoke build tests during spack install")

    # option to init osx sdk env flags
    parser.add_option("--macos-sdk-env-setup",
                      action="store_true",
                      dest="macos_sdk_env_setup",
                      default=False,
                      help="Set several env vars to select OSX SDK settings."
                           "This was necessary for older versions of macOS "
                           " but can cause issues with macOS versions >= 10.13. "
                           " so it is disabled by default.")

    # option to stop after spack download and setup
    parser.add_option("--setup-only",
                      action="store_true",
                      dest="setup_only",
                      default=False,
                      help="Only download and setup Spack. No further Spack command will be run.")


    ###############
    # parse args
    ###############
    opts, extras = parser.parse_args()
    # we want a dict b/c the values could
    # be passed without using optparse
    opts = vars(opts)
    if opts["spack_config_dir"] is not None:
        opts["spack_config_dir"] = pabs(opts["spack_config_dir"])
        if not os.path.isdir(opts["spack_config_dir"]):
            print("[ERROR: invalid spack config dir: {0} ]".format(opts["spack_config_dir"]))
            sys.exit(-1)
    # if rel path is given for the mirror, we need to evaluate here -- before any
    # chdirs to avoid confusion related to what it is relative to.
    # (it should be relative to where uberenv is run from, so it matches what you expect
    #  from shell completion, etc)
    if opts["mirror"] is not None:
        if not opts["mirror"].startswith("http") and not os.path.isabs(opts["mirror"]):
            opts["mirror"] = pabs(opts["mirror"])
    return opts, extras


def pretty_print_dictionary(dictionary):
    for key, value in dictionary.items():
        print("  {0}: {1}".format(key, value))

def uberenv_script_dir():
    # returns the directory of the uberenv.py script
    return os.path.dirname(os.path.abspath(__file__))

def load_json_file(json_file):
    # reads json file
    return json.load(open(json_file))

def is_darwin():
    return "darwin" in platform.system().lower()

def is_windows():
    return "windows" in platform.system().lower()

def find_project_config(opts):
    project_json_file = opts["project_json"]
    # Default case: "project.json" seats next to uberenv.py or is given on command line.
    if os.path.isfile(project_json_file):
        return project_json_file
    # Submodule case: Look for ".uberenv_config.json" in current then search parent dirs
    else:
        lookup_path = pabs(uberenv_script_dir())
        end_of_search = False
        while not end_of_search:
            if os.path.dirname(lookup_path) == lookup_path:
                end_of_search = True
            project_json_file = pjoin(lookup_path,".uberenv_config.json")
            if os.path.isfile(project_json_file):
                return project_json_file
            else:
                lookup_path = pabs(os.path.join(lookup_path, os.pardir))
    print("ERROR: No configuration json file found")
    sys.exit(-1)


class UberEnv():
    """ Base class for package manager """

    def __init__(self, opts, extra_opts):
        self.opts = opts
        self.extra_opts = extra_opts

        # load project settings
        self.project_opts = load_json_file(opts["project_json"])

        # setup main package name
        self.pkg_name = self.set_from_args_or_json("package_name")

        # Set project.json defaults
        if not "force_commandline_prefix" in self.project_opts:
            self.project_opts["force_commandline_prefix"] = False

        print("[uberenv project settings: ")
        pretty_print_dictionary(self.project_opts)
        print("]")

        print("[uberenv command line options: ")
        pretty_print_dictionary(self.opts)
        print("]")

    def setup_paths_and_dirs(self):
        self.uberenv_path = uberenv_script_dir()

        # setup destination paths
        if not self.opts["prefix"]:
            if self.project_opts["force_commandline_prefix"]:
                # project has specified prefix must be on command line
                print("[ERROR: --prefix flag for library destination is required]")
                sys.exit(1)
            # otherwise set default
            self.opts["prefix"] = "uberenv_libs"

        self.dest_dir = pabs(self.opts["prefix"])

        # print a warning if the dest path already exists
        if not os.path.isdir(self.dest_dir):
            os.mkdir(self.dest_dir)
        else:
            print("[info: destination '{0}' already exists]".format(self.dest_dir))

    def set_from_args_or_json(self,setting, optional=True):
        """
        When optional=False: 
            If the setting key is not in the json file, error and raise an exception.
        When optional=True:
            If the setting key is not in the json file or opts, return None.
        """
        setting_value = None
        try:
            setting_value = self.project_opts[setting]
        except (KeyError):
            if not optional:
                print("ERROR: '{0}' must at least be defined in project.json".format(setting))
                raise
        if self.opts[setting]:
            setting_value = self.opts[setting]
        return setting_value

    def set_from_json(self,setting, optional=True):
        """
        When optional=False: 
            If the setting key is not in the json file, error and raise an exception.
        When optional=True:
            If the setting key is not in the json file or opts, return None.
        """
        setting_value = None
        try:
            setting_value = self.project_opts[setting]
        except (KeyError):
            if not optional:
                print("ERROR: '{0}' must at least be defined in project.json".format(setting))
                raise
        return setting_value

    def detect_platform(self):
        # find supported sets of compilers.yaml, packages,yaml
        res = None
        if is_darwin():
            res = "darwin"
        elif "SYS_TYPE" in os.environ.keys():
            sys_type = os.environ["SYS_TYPE"].lower()
            res = sys_type
        return res


class VcpkgEnv(UberEnv):
    """ Helper to clone vcpkg and install libraries on Windows """

    def __init__(self, opts, extra_opts):
        UberEnv.__init__(self,opts,extra_opts)

        # setup architecture triplet
        self.vcpkg_triplet = self.set_from_args_or_json("vcpkg_triplet")
        print("Vcpkg triplet: {0}".format(self.vcpkg_triplet))
        if self.vcpkg_triplet is None:
           self.vcpkg_triplet = os.getenv("VCPKG_DEFAULT_TRIPLET", "x86-windows")

    def setup_paths_and_dirs(self):
        # get the current working path, and the glob used to identify the
        # package files we want to hot-copy to vcpkg

        UberEnv.setup_paths_and_dirs(self)

        # Find path to vcpkg ports
        _errmsg = ""
        if self.opts["vcpkg_ports_path"]:
            # Command line option case
            self.vcpkg_ports_path = pabs(self.opts["vcpkg_ports_path"])
            _errmsg = "Given path for command line option `vcpkg-ports-path` does not exist"
        elif "vcpkg_ports_path" in self.project_opts:
            # .uberenv_config.json case
            new_path = self.project_opts["vcpkg_ports_path"]
            if new_path is not None:
                self.vcpkg_ports_path = pabs(new_path)
            _errmsg = "Given path in config file option 'vcpkg_ports_path' does not exist"
        else:
            # next to uberenv.py script (backwards compatibility)
            self.vcpkg_ports_path = pabs(pjoin(self.uberenv_path, "vcpkg_ports"))
            _errmsg = "Could not find any directory for vcpkg ports. " \
                      "Use either command line option 'vcpkg-ports-path', " \
                      "config file option 'vcpkg_ports_path', or " \
                      "defaulted directory 'vcpkg_ports' next to 'uberenv.py'"

        if not os.path.isdir(self.vcpkg_ports_path):
            print("[ERROR: {0}: {1}]".format(_errmsg, self.vcpkg_ports_path))
            sys.exit(1)

        # setup path for vcpkg repo
        print("[installing to: {0}]".format(self.dest_dir))
        self.dest_vcpkg = pjoin(self.dest_dir,"vcpkg")

        if os.path.isdir(self.dest_vcpkg):
            print("[info: destination '{0}' already exists]".format(self.dest_vcpkg))

    def clone_repo(self):
        if not os.path.isdir(self.dest_vcpkg):
            # compose clone command for the dest path, vcpkg url and branch
            vcpkg_branch = self.project_opts.get("vcpkg_branch", "master")
            vcpkg_url = self.project_opts.get("vcpkg_url", "https://github.com/microsoft/vcpkg")

            print("[info: cloning vcpkg '{0}' branch from {1} into {2}]"
                .format(vcpkg_branch,vcpkg_url, self.dest_vcpkg))

            os.chdir(self.dest_dir)

            clone_opts = ("-c http.sslVerify=false " 
                          if self.opts["ignore_ssl_errors"] else "")

            clone_cmd =  "git {0} clone --single-branch -b {1} {2} vcpkg".format(clone_opts, vcpkg_branch,vcpkg_url)
            sexe(clone_cmd, echo=True)

            # optionally, check out a specific commit
            if "vcpkg_commit" in self.project_opts:
                sha1 = self.project_opts["vcpkg_commit"]
                print("[info: using vcpkg commit {0}]".format(sha1))
                os.chdir(self.dest_vcpkg)
                sexe("git checkout {0}".format(sha1),echo=True)
                
        if self.opts["repo_pull"]:
            # do a pull to make sure we have the latest
            os.chdir(self.dest_vcpkg)
            sexe("git stash", echo=True)
            res = sexe("git pull", echo=True)
            if res != 0:
                #Usually untracked files that would be overwritten
                print("[ERROR: Git failed to pull]")
                sys.exit(-1)


        # Bootstrap vcpkg
        os.chdir(self.dest_vcpkg)
        print("[info: bootstrapping vcpkg]")
        sexe("bootstrap-vcpkg.bat -disableMetrics")

    def patch(self):
        """ hot-copy our ports into vcpkg """
        
        import distutils.dir_util

        dest_vcpkg_ports = pjoin(self.dest_vcpkg, "ports")

        print("[info: copying from {0} to {1}]".format(self.vcpkg_ports_path, dest_vcpkg_ports))
        distutils.dir_util.copy_tree(self.vcpkg_ports_path, dest_vcpkg_ports)


    def clean_build(self):
        pass

    def show_info(self):
        os.chdir(self.dest_vcpkg)
        print("[info: Details for package '{0}']".format(self.pkg_name))
        sexe("vcpkg.exe search " + self.pkg_name, echo=True)

        print("[info: Dependencies for package '{0}']".format(self.pkg_name))
        sexe("vcpkg.exe depend-info " + self.pkg_name, echo=True)

    def create_mirror(self):
        pass

    def use_mirror(self):
        pass

    def install(self):
        
        os.chdir(self.dest_vcpkg)
        install_cmd = "vcpkg.exe "
        install_cmd += "install {0}:{1}".format(self.pkg_name, self.vcpkg_triplet)

        res = sexe(install_cmd, echo=True)

        # Running the install_cmd eventually generates the host config file,
        # which we copy to the target directory.
        src_hc = pjoin(self.dest_vcpkg, "installed", self.vcpkg_triplet, "include", self.pkg_name, "hc.cmake")
        hcfg_fname = pjoin(self.dest_dir, "{0}.{1}.cmake".format(platform.uname()[1], self.vcpkg_triplet))
        print("[info: copying host config file to {0}]".format(hcfg_fname))
        shutil.copy(os.path.abspath(src_hc), hcfg_fname)
        print("")
        print("[install complete!]")
        return res


class SpackEnv(UberEnv):
    """ Helper to clone spack and install libraries on MacOS an Linux """

    def __init__(self, opts, extra_opts):
        UberEnv.__init__(self,opts,extra_opts)

        self.spack_cmd = "spack/bin/spack"

        self.pkg_version = self.set_from_json("package_version")
        self.pkg_src_dir = self.set_from_args_or_json("package_source_dir")
        self.pkg_final_phase = self.set_from_args_or_json("package_final_phase",True)
        # get build mode
        self.build_mode = self.set_from_args_or_json("spack_build_mode",True)
        # default spack build mode is dev-build
        if self.build_mode is None:
            self.build_mode = "dev-build"
        # NOTE: install always overrides the build mode to "install"
        if self.opts["install"]:
            self.build_mode = "install"
        # if we are using fake package mode, adjust the pkg name
        if self.build_mode == "uberenv-pkg":
            self.pkg_name =  "uberenv-" + self.pkg_name

        print("[uberenv spack build mode: {0}]".format(self.build_mode))
        self.packages_paths = []
        self.spec_hash = ""
        self.use_install = False

        # Some additional setup for macos
        if is_darwin():
            if opts["macos_sdk_env_setup"]:
                # setup osx deployment target and sdk settings
                setup_osx_sdk_env_vars()
            else:
                print("[skipping MACOSX env var setup]")

        # setup default spec
        if opts["spec"] is None:
            if is_darwin():
                opts["spec"] = "%clang"
            else:
                opts["spec"] = "%gcc"
            self.opts["spec"] = "@{0}{1}".format(self.pkg_version,opts["spec"])
        elif not opts["spec"].startswith("@"):
            self.opts["spec"] = "@{0}{1}".format(self.pkg_version,opts["spec"])
        else:
            self.opts["spec"] = "{0}".format(opts["spec"])

        print("[spack spec: {0}]".format(self.opts["spec"]))

    def print_spack_python_info(self):
        spack_dir = self.dest_spack
        cmd = pjoin(spack_dir,"bin","spack")
        cmd += " python "
        cmd += '-c "import sys; print(sys.executable);"'
        res, out = sexe( cmd, ret_output = True)
        print("[spack python: {0}]".format(out.strip()))

    def append_path_to_packages_paths(self, path, errorOnNonexistant=True):
        path = pabs(path)
        if not os.path.exists(path):
            if errorOnNonexistant:
                print("[ERROR: Given path in 'spack_packages_path' does not exist: {0}]".format(path))
                sys.exit(1)
            else:
                return
        self.packages_paths.append(path)


    def setup_paths_and_dirs(self):
        # get the current working path, and the glob used to identify the
        # package files we want to hot-copy to spack

        UberEnv.setup_paths_and_dirs(self)

        # Find Spack yaml configs path (compilers.yaml, packages.yaml, etc.)

        # Next to uberenv.py (backwards compatility)
        spack_configs_path = pabs(pjoin(self.uberenv_path,"spack_configs"))

        # In project config file
        if "spack_configs_path" in self.project_opts.keys():
            new_path = self.project_opts["spack_configs_path"]
            if new_path is not None:
                spack_configs_path = pabs(new_path)
                if not os.path.isdir(spack_configs_path):
                    print("[ERROR: Given path in 'spack_configs_path' does not exist: {0}]".format(spack_configs_path))
                    sys.exit(1)

        # Test if the override option was used (--spack-config-dir)
        self.spack_config_dir = self.opts["spack_config_dir"]
        if self.spack_config_dir is None:
            # If command line option is not used, search for platform under
            # given directory
            uberenv_plat = self.detect_platform()
            if uberenv_plat is not None:
                self.spack_config_dir = pabs(pjoin(spack_configs_path,uberenv_plat))

        # Find project level packages to override spack's internal packages
        if "spack_packages_path" in self.project_opts.keys():
            # packages directories listed in project.json
            _paths = self.project_opts["spack_packages_path"]
            if not isinstance(_paths, list):
                # user gave a single string
                self.append_path_to_packages_paths(_paths)
            else:
                # user gave a list of strings
                for _path in _paths:
                    self.append_path_to_packages_paths(_path)
        else:
            # default to packages living next to uberenv script if it exists
            self.append_path_to_packages_paths(pjoin(self.uberenv_path,"packages"), errorOnNonexistant=False)

        print("[installing to: {0}]".format(self.dest_dir))

        self.dest_spack = pjoin(self.dest_dir,"spack")
        if os.path.isdir(self.dest_spack):
            print("[info: destination '{0}' already exists]".format(self.dest_spack))

        self.pkg_src_dir = os.path.abspath(os.path.join(self.dest_dir,self.pkg_src_dir))
        if not os.path.isdir(self.pkg_src_dir):
            print("[ERROR: package_source_dir '{0}' does not exist]".format(self.pkg_src_dir))
            sys.exit(-1)

    def find_spack_pkg_path_from_hash(self, pkg_name, pkg_hash):
        res, out = sexe("{0} find -p /{1}".format(self.spack_cmd, pkg_hash), ret_output = True)
        for l in out.split("\n"):
            if l.startswith(pkg_name):
                   return {"name": pkg_name, "path": l.split()[-1]}
        print("[ERROR: failed to find package named '{0}']".format(pkg_name))
        sys.exit(-1)

    def find_spack_pkg_path(self, pkg_name, spec = ""):
        res, out = sexe("{0} find -p {1}".format(self.spack_cmd, pkg_name + spec), ret_output = True)
        for l in out.split("\n"):
            # TODO: at least print a warning when several choices exist. This will
            # pick the first in the list.
            if l.startswith(pkg_name):
                   return {"name": pkg_name, "path": l.split()[-1]}
        print("[ERROR: failed to find package named '{0}']".format(pkg_name))
        sys.exit(-1)

    # Extract the first line of the full spec
    def read_spack_full_spec(self,pkg_name,spec):
        res, out = sexe("{0} spec {1} {2}".format(self.spack_cmd, pkg_name, spec), ret_output=True)
        for l in out.split("\n"):
            if l.startswith(pkg_name) and l.count("@") > 0 and l.count("arch=") > 0:
                return l.strip()

    def clone_repo(self):
        if not os.path.isdir(self.dest_spack):

            # compose clone command for the dest path, spack url and branch
            print("[info: cloning spack develop branch from github]")

            os.chdir(self.dest_dir)

            clone_opts = ("-c http.sslVerify=false "
                          if self.opts["ignore_ssl_errors"] else "")

            spack_url = self.project_opts.get("spack_url", "https://github.com/spack/spack.git")
            spack_branch = self.project_opts.get("spack_branch", "develop")

            clone_cmd =  "git {0} clone --single-branch --depth=1 -b {1} {2} spack".format(clone_opts, spack_branch, spack_url)
            sexe(clone_cmd, echo=True)

        if "spack_commit" in self.project_opts:
            # optionally, check out a specific commit
            os.chdir(pjoin(self.dest_dir,"spack"))
            sha1 = self.project_opts["spack_commit"]
            res, current_sha1 = sexe("git log -1 --pretty=%H", ret_output=True)
            if sha1 != current_sha1:
                print("[info: using spack commit {0}]".format(sha1))
                sexe("git stash", echo=True)
                sexe("git fetch --depth=1 origin {0}".format(sha1),echo=True)
                res = sexe("git checkout {0}".format(sha1),echo=True)
                if res != 0:
                    # Usually untracked files that would be overwritten
                    print("[ERROR: Git failed to checkout]")
                    sys.exit(-1)

        if self.opts["repo_pull"]:
            # do a pull to make sure we have the latest
            os.chdir(pjoin(self.dest_dir,"spack"))
            sexe("git stash", echo=True)
            res = sexe("git pull", echo=True)
            if res != 0:
                #Usually untracked files that would be overwritten
                print("[ERROR: Git failed to pull]")
                sys.exit(-1)

    def load(self):
        # load spack environment, potentially overriding spack defaults
        # uberenv used to handle defaults overriding, now spack environment can
        # be used to do so, but it relies on each project to make sure their
        # environment is well designed.

        self.spack_cmd = "{0} -e {1}".format(self.spack_cmd,self.config_dir())

        # A simple proxy script for spack
        uber_spack='#!/bin/bash\n$(dirname ${{0}})/{0} "$@"\n'.format(self.spack_cmd)

        with open('uber-spack','w+') as script:
            script.write(uber_spack)

        # Making the script executable
        st = os.stat('uber-spack')
        os.chmod('uber-spack', st.st_mode | stat.S_IEXEC)


# TODO: To keep or not to keep?
        # this is an opportunity to show spack python info post obtaining spack
        self.print_spack_python_info()


        # hot-copy our packages into spack
        if len(self.packages_paths) > 0:
            dest_spack_pkgs = pjoin(self.dest_spack,"var","spack","repos","builtin","packages")
            for _base_path in self.packages_paths:
                _src_glob = pjoin(_base_path, "*")
                print("[copying patched packages from {0}]".format(_src_glob))
                sexe("cp -Rf {0} {1}".format(_src_glob, dest_spack_pkgs))



    def clean_build(self):
        # clean out any temporary spack build stages
        cln_cmd = "{0} clean ".format(self.spack_cmd)
        res = sexe(cln_cmd, echo=True)

        # clean out any spack cached stuff
        cln_cmd = "{0} clean --all".format(self.spack_cmd)
        res = sexe(cln_cmd, echo=True)

        # check if we need to force uninstall of selected packages
        if self.opts["spack_clean"]:
            if self.project_opts.has_key("spack_clean_packages"):
                for cln_pkg in self.project_opts["spack_clean_packages"]:
                    if self.find_spack_pkg_path(cln_pkg) is not None:
                        uninst_cmd = "{0} uninstall -f -y --all --dependents ".format(self.spack_cmd) + cln_pkg
                        res = sexe(uninst_cmd, echo=True)

    def show_info(self):
        # print concretized spec with install info
        # default case prints install status and 32 characters hash
        options="--install-status --very-long"
        spec_cmd = "{0} spec {1} {2}{3}".format(self.spack_cmd,options,self.pkg_name,self.opts["spec"])

        res, out = sexe(spec_cmd, ret_output=True, echo=True)
        print(out)

        #Check if spec is already installed
        for line in out.split("\n"):
            # Example of matching line: ("status"  "hash"  "package"...)
            # [+]  hf3cubkgl74ryc3qwen73kl4yfh2ijgd  serac@develop%clang@10.0.0-apple~debug~devtools~glvis arch=darwin-mojave-x86_64
            if re.match(r"^(\[\+\]| - )  [a-z0-9]{32}  " + re.escape(self.pkg_name), line):
                self.spec_hash = line.split("  ")[1]
                # if spec already installed
                if line.startswith("[+]"):
                    pkg_path = self.find_spack_pkg_path_from_hash(self.pkg_name,self.spec_hash)
                    install_path = pkg_path["path"]
                    # testing that the path exists is mandatory until Spack team fixes
                    # https://github.com/spack/spack/issues/16329
                    if os.path.isdir(install_path):
                        print("[Warning: {0} {1} has already been installed in {2}]".format(self.pkg_name, self.opts["spec"],install_path))
                        print("[Warning: Uberenv will proceed using this directory]".format(self.pkg_name))
                        self.use_install = True

        return res

    def install(self):
        # use the uberenv package to trigger the right builds
        # and build an host-config.cmake file
        if not self.use_install:
            install_cmd = "{0} ".format(self.spack_cmd)
            if self.opts["ignore_ssl_errors"]:
                install_cmd += "-k "
            # build mode -- install path
            if self.build_mode == "install":
                install_cmd += "install "
                if self.opts["run_tests"]:
                    install_cmd += "--test=root "
            # build mode - dev build path
            elif self.build_mode == "dev-build":
                # dev build path
                install_cmd += "dev-build --quiet -d {0} ".format(self.pkg_src_dir)
                if self.pkg_final_phase:
                    install_cmd += "-u {0} ".format(self.pkg_final_phase)
            # build mode -- original fake package path
            elif self.build_mode == "uberenv-pkg":
                install_cmd += "install "
                if self.pkg_final_phase:
                    install_cmd += "-u {0} ".format(self.pkg_final_phase)
            else:
                print("[ERROR: unsupported build mode: {0}]".format(self.build_mode))
                return -1
            if self.opts["build_jobs"]:
                install_cmd += "-j {0} ".format(self.opts["build_jobs"])
            # for all cases we use the pkg name and spec
            install_cmd += self.pkg_name + self.opts["spec"]
            res = sexe(install_cmd, echo=True)
            if res != 0:
                print("[ERROR: failure of spack install/dev-build]")
                return res

        full_spec = self.read_spack_full_spec(self.pkg_name,self.opts["spec"])
        if "spack_activate" in self.project_opts:
            print("[activating dependent packages]")
            # get the full spack spec for our project
            pkg_names = self.project_opts["spack_activate"].keys()
            for pkg_name in pkg_names:
                pkg_spec_requirements = self.project_opts["spack_activate"][pkg_name]
                activate=True
                for req in pkg_spec_requirements:
                    if req not in full_spec:
                        activate=False
                        break
                if activate:
                    activate_cmd = "{0} activate {1}".format(self.spack_cmd,pkg_name)
                    res = sexe(activate_cmd, echo=True)
                    if res != 0:
                      return res
            print("[done activating dependent packages]")
        # note: this assumes package extends python when +python
        # this may fail general cases
        if self.build_mode == "install" and "+python" in full_spec:
            activate_cmd = "{0} activate /{1}".format(self.spack_cmd, self.spec_hash)
            res = sexe(activate_cmd, echo=True)
            if res != 0:
              return res
        # when using install or uberenv-pkg mode, create a symlink to the host config 
        if self.build_mode == "install" or \
           self.build_mode == "uberenv-pkg" \
           or self.use_install:
            # use spec_hash to locate b/c other helper won't work if complex
            # deps are provided in the spec (e.g: @ver+variant ^package+variant)
            pkg_path = self.find_spack_pkg_path_from_hash(self.pkg_name, self.spec_hash)
            if self.pkg_name != pkg_path["name"]:
                print("[ERROR: Could not find install of {0} with hash {1}]".format(self.pkg_name,self.spec_hash))
                return -1
            else:
                # Symlink host-config file
                hc_glob = glob.glob(pjoin(pkg_path["path"],"*.cmake"))
                if len(hc_glob) > 0:
                    hc_path  = hc_glob[0]
                    hc_fname = os.path.split(hc_path)[1]
                    if os.path.islink(hc_fname):
                        os.unlink(hc_fname)
                    elif os.path.isfile(hc_fname):
                        sexe("rm -f {0}".format(hc_fname))
                    print("[symlinking host config file to {0}]".format(pjoin(self.dest_dir,hc_fname)))
                    os.symlink(hc_path,hc_fname)
                # if user opt'd for an install, we want to symlink the final
                # install to an easy place:
                # Symlink install directory
                if self.build_mode == "install":
                    pkg_lnk_dir = "{0}-install".format(self.pkg_name)
                    if os.path.islink(pkg_lnk_dir):
                        os.unlink(pkg_lnk_dir)
                    print("")
                    print("[symlinking install to {0}]".format(pjoin(self.dest_dir,pkg_lnk_dir)))
                    os.symlink(pkg_path["path"],pabs(pkg_lnk_dir))
                    print("")
                    print("[install complete!]")
        elif self.build_mode == "dev-build":
                # we are in the "only dependencies" dev build case and the host-config
                # file has to be copied from the do-be-deleted spack-build dir.
                build_base = pjoin(self.dest_dir,"{0}-build".format(self.pkg_name))
                build_dir  = pjoin(build_base,"spack-build")
                pattern = "*{0}.cmake".format(self.pkg_name)
                build_dir = pjoin(self.pkg_src_dir,"spack-build")
                hc_glob = glob.glob(pjoin(build_dir,pattern))
                if len(hc_glob) > 0:
                    hc_path  = hc_glob[0]
                    hc_fname = os.path.split(hc_path)[1]
                    if os.path.islink(hc_fname):
                        os.unlink(hc_fname)
                    print("[copying host config file to {0}]".format(pjoin(self.dest_dir,hc_fname)))
                    sexe("cp {0} {1}".format(hc_path,hc_fname))
                    print("[removing project build directory {0}]".format(pjoin(build_dir)))
                    sexe("rm -rf {0}".format(build_dir))
        else:
            print("[ERROR: Unsupported build mode {0}]".format(self.build_mode))
            return -1

    def get_mirror_path(self):
        mirror_path = self.opts["mirror"]
        if not mirror_path:
            print("[--create-mirror requires a mirror directory]")
            sys.exit(-1)
        return mirror_path

    def create_mirror(self):
        """
        Creates a spack mirror for pkg_name at mirror_path.
        """

        mirror_path = self.get_mirror_path()

        mirror_cmd = self.spack_cmd()
        if self.opts["ignore_ssl_errors"]:
            mirror_cmd += "-k "
        mirror_cmd += "mirror create -d {0} --dependencies {1}{2}".format(mirror_path,
                                                                    self.pkg_name,
                                                                    self.opts["spec"])
        return sexe(mirror_cmd, echo=True)

    def find_spack_mirror(self, mirror_name):
        """
        Returns the path of a defaults scoped spack mirror with the
        given name, or None if no mirror exists.
        """
        res, out = sexe("{0} mirror list".format(self.spack_cmd), ret_output=True)
        mirror_path = None
        for mirror in out.split('\n'):
            if mirror:
                parts = mirror.split()
                if parts[0] == mirror_name:
                    mirror_path = parts[1]
        return mirror_path

    def use_mirror(self):
        """
        Configures spack to use mirror at a given path.
        """
        mirror_name = self.pkg_name
        mirror_path = self.get_mirror_path()
        existing_mirror_path = self.find_spack_mirror(mirror_name)

        if existing_mirror_path and mirror_path != existing_mirror_path:
            # Existing mirror has different URL, error out
            print("[removing existing spack mirror `{0}` @ {1}]".format(mirror_name,
                                                                        existing_mirror_path))
            #
            # Note: In this case, spack says it removes the mirror, but we still
            # get errors when we try to add a new one, sounds like a bug
            #
            sexe("{0} mirror remove --scope=defaults {1} ".format(self.spack_cmd,mirror_name),
                echo=True)
            existing_mirror_path = None
        if not existing_mirror_path:
            # Add if not already there
            sexe("{1} mirror add --scope=defaults {1} {2}".format(
                    mirror_name, mirror_path), echo=True)
            print("[using mirror {0}]".format(mirror_path))

    def find_spack_upstream(self, upstream_name):
        """
        Returns the path of a defaults scoped spack upstream with the
        given name, or None if no upstream exists.
        """
        upstream_path = None

        res, out = sexe('{0} config get upstreams'.format(self.spack_cmd), ret_output=True)
        if (not out) and ("upstreams:" in out):
            out = out.replace(' ', '')
            out = out.replace('install_tree:', '')
            out = out.replace(':', '')
            out = out.splitlines()
            out = out[1:]
            upstreams = dict(zip(out[::2], out[1::2]))

            for name in upstreams.keys():
                if name == upstream_name:
                    upstream_path = upstreams[name]

        return upstream_path

    def use_spack_upstream(self):
        """
        Configures spack to use upstream at a given path.
        """
        upstream_path = self.opts["upstream"]
        if not upstream_path:
            print("[--create-upstream requires a upstream directory]")
            sys.exit(-1)
        upstream_path = pabs(upstream_path)
        upstream_name = self.pkg_name
        existing_upstream_path = self.find_spack_upstream(upstream_name)
        if (not existing_upstream_path) or (upstream_path != pabs(existing_upstream_path)):
            # Existing upstream has different URL, error out
            print("[removing existing spack upstream configuration file]")
            sexe("rm spack/etc/spack/defaults/upstreams.yaml")
            with open('spack/etc/spack/defaults/upstreams.yaml','w+') as upstreams_cfg_file:
                upstreams_cfg_file.write("upstreams:\n")
                upstreams_cfg_file.write("  {0}:\n".format(upstream_name))
                upstreams_cfg_file.write("    install_tree: {0}\n".format(upstream_path))


def find_osx_sdks():
    """
    Finds installed osx sdks, returns dict mapping version to file system path
    """
    res = {}
    sdks = glob.glob("/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX*.sdk")
    for sdk in sdks:
        sdk_base = os.path.split(sdk)[1]
        ver = sdk_base[len("MacOSX"):sdk_base.rfind(".")]
        res[ver] = sdk
    return res

def setup_osx_sdk_env_vars():
    """
    Finds installed osx sdks, returns dict mapping version to file system path
    """
    # find current osx version (10.11.6)
    dep_tgt = platform.mac_ver()[0]
    # sdk file names use short version (ex: 10.11)
    dep_tgt_short = dep_tgt[:dep_tgt.rfind(".")]
    # find installed sdks, ideally we want the sdk that matches the current os
    sdk_root = None
    sdks = find_osx_sdks()
    if dep_tgt_short in sdks.keys():
        # matches our osx, use this one
        sdk_root = sdks[dep_tgt_short]
    elif len(sdks) > 0:
        # for now, choose first one:
        dep_tgt  = sdks.keys()[0]
        sdk_root = sdks[dep_tgt]
    else:
        # no valid sdks, error out
        print("[ERROR: Could not find OSX SDK @ /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/]")
        sys.exit(-1)

    env["MACOSX_DEPLOYMENT_TARGET"] = dep_tgt
    env["SDKROOT"] = sdk_root
    print("[setting MACOSX_DEPLOYMENT_TARGET to {0}]".format(env["MACOSX_DEPLOYMENT_TARGET"]))
    print("[setting SDKROOT to {0}]".format(env[ "SDKROOT"]))


def print_uberenv_python_info():
    print("[uberenv python: {0}]".format(sys.executable))


def main():
    """
    Clones and runs a package manager to setup third_party libs.
    Also creates a host-config.cmake file that can be used by our project.
    """

    print_uberenv_python_info()

    # parse args from command line
    opts, extra_opts = parse_args()

    # project options
    opts["project_json"] = find_project_config(opts)

    # Initialize the environment -- use vcpkg on windows, spack otherwise
    env = SpackEnv(opts, extra_opts) if not is_windows() else VcpkgEnv(opts, extra_opts)

    # Setup the necessary paths and directories
    env.setup_paths_and_dirs()

    # Clone the package manager
    env.clone_repo()

    os.chdir(env.dest_dir)

    # Patch the package manager, as necessary
    if not is_windows():
      env.load()
    else:
      env.patch()

    # Clean the build
    env.clean_build()

    # Allow to end uberenv after spack is ready
    if opts["setup_only"]:
        return 0

    # Show the spec for what will be built
    env.show_info()


    ###########################################################
    # we now have an instance of our package manager configured
    # how we need it to build our tpls. At this point there are
    # two possible next steps:
    #
    # *) create a mirror of the packages
    #   OR
    # *) build
    #
    ###########################################################
    if opts["create_mirror"]:
        return env.create_mirror()
    else:
        if opts["mirror"] is not None:
            env.use_mirror()

        if opts["upstream"] is not None:
            env.use_spack_upstream()

        res = env.install()

        return res

if __name__ == "__main__":
    sys.exit(main())

