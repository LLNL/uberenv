#!/bin/sh
"exec" "python3" "-u" "-B" "$0" "$@"
###############################################################################
# Copyright (c) 2014-2025, Lawrence Livermore National Security, LLC.
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
import subprocess
import shutil
import socket
import platform
import json
import glob
import re
import argparse

from functools import partial

from os import environ as env
from os.path import join as pjoin
from os.path import abspath as pabs

# Since we use subprocesses, flushing prints allows us to keep logs in
# order.
print = partial(print, flush=True)

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--install",
                      action="store_true",
                      dest="install",
                      default=False,
                      help="Install `package_name`, not just its dependencies.")

    # where to install
    parser.add_argument("--prefix",
                      dest="prefix",
                      default=None,
                      help="destination directory")

    # Spack spec without preceding package name
    parser.add_argument("--spec",
                      dest="spec",
                      default=None,
                      help="Spack spec without preceding package name")

    # for vcpkg, what architecture to target
    parser.add_argument("--triplet",
                      dest="vcpkg_triplet",
                      default=None,
                      help="vcpkg architecture triplet")

    # optional location of spack mirror
    parser.add_argument("--mirror",
                      dest="mirror",
                      default=None,
                      help="spack mirror directory")

    # flag to create mirror
    parser.add_argument("--create-mirror",
                      action="store_true",
                      dest="create_mirror",
                      default=False,
                      help="Create spack mirror")

    # optional location of spack upstream
    parser.add_argument("--upstream",
                      dest="upstream",
                      default=None,
                      help="add an external spack instance as upstream")

    # optional spack --reuse concretizer behaviour
    parser.add_argument("--reuse",
                      dest="reuse",
                      default=False,
                      help="Use spack v0.17+ --reuse functionality for spec, install and dev-build.")

    # this option allows a user to set the directory for their vcpkg ports on Windows
    parser.add_argument("--vcpkg-ports-path",
                      dest="vcpkg_ports_path",
                      default=None,
                      help="dir with vckpkg ports")

    # overrides package_name
    parser.add_argument("--package-name",
                      dest="package_name",
                      default=None,
                      help="override the default package name")

    # uberenv spack tpl build mode
    parser.add_argument("--spack-build-mode",
                      dest="spack_build_mode",
                      default=None,
                      help="set mode used to build third party dependencies with spack"
                           "(options: 'dev-build' 'uberenv-pkg' 'install' "
                           "[default: 'dev-build'] )\n")

    # spack debug mode
    parser.add_argument("--spack-debug",
                      dest="spack_debug",
                      action="store_true",
                      default=False,
                      help="add debug option to all spack commands")

    # spack allow deprecated packages
    parser.add_argument("--spack-allow-deprecated",
                      dest="spack_allow_deprecated",
                      action="store_true",
                      default=False,
                      help="add --deprecated to spack install commands")

    # controls after which package phase spack should stop
    parser.add_argument("--package-final-phase",
                      dest="package_final_phase",
                      default=None,
                      help="override the default phase after which spack should stop")

    # controls source_dir spack should use to build the package
    parser.add_argument("--package-source-dir",
                      dest="package_source_dir",
                      default=None,
                      help="override the default source dir spack should use")

    # a file that holds settings for a specific project
    # using uberenv.py
    parser.add_argument("--project-json",
                      dest="project_json",
                      default=pjoin(uberenv_script_dir(),"project.json"),
                      help="uberenv project settings json file")

    # option to explicitly set the number of build jobs
    parser.add_argument("-j",
                      dest="build_jobs",
                      default=None,
                      help="Explicitly set build jobs")

    # flag to use insecure curl + git
    parser.add_argument("-k",
                      action="store_true",
                      dest="ignore_ssl_errors",
                      default=False,
                      help="Ignore SSL Errors")

    # option to force a pull of the package manager
    parser.add_argument("--pull",
                      action="store_true",
                      dest="repo_pull",
                      default=False,
                      help="Pull from package manager, if repo already exists")

    # option to force for clean of packages specified to
    # be cleaned in the project.json
    parser.add_argument("--clean",
                      action="store_true",
                      dest="spack_clean",
                      default=False,
                      help="Force uninstall of packages specified in project.json")

    # option to tell spack to run tests
    parser.add_argument("--run_tests",
                      action="store_true",
                      dest="run_tests",
                      default=False,
                      help="Invoke build tests during spack install")

    # option to init osx sdk env flags
    parser.add_argument("--macos-sdk-env-setup",
                      action="store_true",
                      dest="macos_sdk_env_setup",
                      default=False,
                      help="Set several env vars to select OSX SDK settings."
                           "This was necessary for older versions of macOS "
                           " but can cause issues with macOS versions >= 10.13. "
                           " so it is disabled by default.")

    # option to stop after spack download and setup
    parser.add_argument("--setup-only",
                      action="store_true",
                      dest="setup_only",
                      default=False,
                      help="Only download and setup the package manager. No further Spack command will be run. Will not create Spack Environment.")

    # option to stop after spack env creation
    parser.add_argument("--setup-and-env-only",
                      action="store_true",
                      dest="setup_and_env_only",
                      default=False,
                      help="Download and setup the package manager, create a Spack Environment. No further Spack command will be run.")

    # option to skip spack download and setup
    parser.add_argument("--skip-setup",
                      action="store_true",
                      dest="skip_setup",
                      default=False,
                      help="Only create env and install (using pre-setup Spack).")

    # option to skip spack download, setup and env creation
    parser.add_argument("--skip-setup-and-env",
                      action="store_true",
                      dest="skip_setup_and_env",
                      default=False,
                      help="Only install (using pre-setup Spack and environment).")

    # Spack externals list
    parser.add_argument("--spack-externals",
                      dest="spack_externals",
                      default=None,
                      nargs="+",
                      help="Space delimited string of packages for Spack to search for externals (if no spack_env_file is found)")

    # Spack compiler paths list
    parser.add_argument("--spack-compiler-paths",
                      dest="spack_compiler_paths",
                      default=None,
                      nargs="+",
                      help="Space delimited string of paths for Spack to search for compilers (if no spack_env_file is found)")

    # Spack Environment name
    parser.add_argument("--spack-env-name",
                      dest="spack_env_name",
                      default="spack_env",
                      help="The name of the Spack Environment, which will be created in prefix directory.")

    # Spack Environment file
    parser.add_argument("--spack-env-file",
                      dest="spack_env_file",
                      default=None,
                      help="Path to Spack Environment file (e.g. spack.yaml or spack.lock)")

    ###############
    # parse args
    ###############
    args, extra_args = parser.parse_known_args()
    # we want a dict b/c the values could
    # be passed without using optparse
    args = vars(args)

    # if rel path is given for the mirror, we need to evaluate here -- before any
    # chdirs to avoid confusion related to what it is relative to.
    # (it should be relative to where uberenv is run from, so it matches what you expect
    #  from shell completion, etc)
    if not is_windows() and args["mirror"] is not None:
        if not args["mirror"].startswith(("http","oci")) and not os.path.isabs(args["mirror"]):
            args["mirror"] = pabs(args["mirror"])
    return args, extra_args

def have_internet(host="llnl.gov", port=80, timeout=3):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        return True
    except:
        return False
    finally:
        s.close()

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

def find_project_config(args):
    project_json_file = args["project_json"]
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
    print("ERROR: No Uberenv configuration json file found")
    sys.exit(-1)


class UberEnv():
    """ Base class for package manager """

    def __init__(self, args, extra_args):
        self.args = args
        self.extra_args = extra_args

        # load project settings
        self.project_args = load_json_file(args["project_json"])

        # setup main package name
        self.pkg_name = self.set_from_args_or_json("package_name")

        # Set project.json defaults
        if not "force_commandline_prefix" in self.project_args:
            self.project_args["force_commandline_prefix"] = False

        print("[uberenv project settings: ")
        pretty_print_dictionary(self.project_args)
        print("]")

        print("[uberenv command line options: ")
        pretty_print_dictionary(self.args)
        print("]")

    def setup_paths_and_dirs(self):
        self.uberenv_path = uberenv_script_dir()

        # setup destination paths
        if not self.args["prefix"]:
            if self.project_args["force_commandline_prefix"]:
                # project has specified prefix must be on command line
                print("[ERROR: --prefix flag for library destination is required]")
                sys.exit(-1)
            # otherwise set default
            self.args["prefix"] = "uberenv_libs"

        self.dest_dir = pabs(self.args["prefix"])

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
            If the setting key is not in the json file or args, return None.
        """
        setting_value = None
        try:
            setting_value = self.project_args[setting]
        except (KeyError):
            if not optional:
                print("ERROR: '{0}' must at least be defined in project.json".format(setting))
                raise
        if self.args[setting]:
            setting_value = self.args[setting]
        return setting_value

    def set_from_json(self,setting, optional=True):
        """
        When optional=False: 
            If the setting key is not in the json file, error and raise an exception.
        When optional=True:
            If the setting key is not in the json file or args, return None.
        """
        setting_value = None
        try:
            setting_value = self.project_args[setting]
        except (KeyError):
            if not optional:
                print("ERROR: '{0}' must at least be defined in project.json".format(setting))
                raise
        return setting_value

    def detect_platform(self):
        # find supported spack.yaml
        if is_darwin():
            return "darwin"
        elif "SYS_TYPE" in os.environ.keys():
            return os.environ["SYS_TYPE"].lower()
        else:
            return None


class VcpkgEnv(UberEnv):
    """ Helper to clone vcpkg and install libraries on Windows """

    def __init__(self, args, extra_args):
        UberEnv.__init__(self,args,extra_args)

        # setup architecture triplet
        self.vcpkg_triplet = self.set_from_args_or_json("vcpkg_triplet")
        print("Vcpkg triplet: {}".format(self.vcpkg_triplet))
        if self.vcpkg_triplet is None:
           self.vcpkg_triplet = os.getenv("VCPKG_DEFAULT_TRIPLET", "x86-windows")

    def setup_paths_and_dirs(self):
        # get the current working path, and the glob used to identify the
        # package files we want to hot-copy to vcpkg

        UberEnv.setup_paths_and_dirs(self)

        # Find path to vcpkg ports
        _errmsg = ""
        if self.args["vcpkg_ports_path"]:
            # Command line option case
            self.vcpkg_ports_path = pabs(self.args["vcpkg_ports_path"])
            _errmsg = "Given path for command line option `vcpkg-ports-path` does not exist"
        elif "vcpkg_ports_path" in self.project_args:
            # .uberenv_config.json case
            new_path = self.project_args["vcpkg_ports_path"]
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
            sys.exit(-1)

        # setup path for vcpkg repo
        print("[installing to: {0}]".format(self.dest_dir))
        self.dest_vcpkg = pjoin(self.dest_dir,"vcpkg")

        if os.path.isdir(self.dest_vcpkg):
            print("[info: destination '{0}' already exists]".format(self.dest_vcpkg))

    def clone_repo(self):
        if not os.path.isdir(self.dest_vcpkg):
            # compose clone command for the dest path, vcpkg url and branch
            vcpkg_branch = self.project_args.get("vcpkg_branch", "master")
            vcpkg_url = self.project_args.get("vcpkg_url", "https://github.com/microsoft/vcpkg")

            print("[info: cloning vcpkg '{0}' branch from {1} into {2}]"
                .format(vcpkg_branch,vcpkg_url, self.dest_vcpkg))

            os.chdir(self.dest_dir)

            clone_args = ("-c http.sslVerify=false " 
                          if self.args["ignore_ssl_errors"] else "")

            clone_cmd =  "git {0} clone --single-branch -b {1} {2} vcpkg".format(clone_args, vcpkg_branch,vcpkg_url)
            sexe(clone_cmd, echo=True)

            # optionally, check out a specific commit
            if "vcpkg_commit" in self.project_args:
                sha1 = self.project_args["vcpkg_commit"]
                print("[info: using vcpkg commit {0}]".format(sha1))
                os.chdir(self.dest_vcpkg)
                sexe("git checkout {0}".format(sha1),echo=True)

        if self.args["repo_pull"]:
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

        dest_vcpkg_ports = pjoin(self.dest_vcpkg, "ports")

        print("[info: copying from {0} to {1}]".format(self.vcpkg_ports_path, dest_vcpkg_ports))
        shutil.copytree(self.vcpkg_ports_path, dest_vcpkg_ports, dirs_exist_ok=True)


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

    def __init__(self, args, extra_args):
        UberEnv.__init__(self,args,extra_args)

        self.pkg_version = self.set_from_json("package_version")
        self.pkg_src_dir = self.set_from_args_or_json("package_source_dir", True)
        self.pkg_final_phase = self.set_from_args_or_json("package_final_phase", True)
        self.build_mode = self.set_from_args_or_json("spack_build_mode", True)
        self.spack_externals = self.set_from_args_or_json("spack_externals", True)
        self.spack_compiler_paths = self.set_from_args_or_json("spack_compiler_paths", True)

        # default spack build mode is dev-build
        if self.build_mode is None:
            self.build_mode = "dev-build"
        # NOTE: install always overrides the build mode to "install"
        if self.args["install"]:
            self.build_mode = "install"
        # if we are using fake package mode, adjust the pkg name
        if self.build_mode == "uberenv-pkg":
            self.pkg_name =  "uberenv-" + self.pkg_name
        # convert lists to space-delimited string
        if type(self.spack_externals) is list:
            self.spack_externals = " ".join(self.spack_externals)
        if type(self.spack_compiler_paths) is list:
            self.spack_compiler_paths = " ".join(self.spack_compiler_paths)

        # Whether or not to generate a spack.yaml
        self.spack_setup_environment = False

        print("[uberenv spack build mode: {0}]".format(self.build_mode))
        self.packages_paths = []
        self.spec_hash = ""
        self.use_install = False

        # Some additional setup for macos
        if is_darwin():
            if args["macos_sdk_env_setup"]:
                # setup osx deployment target and sdk settings
                setup_osx_sdk_env_vars()
            else:
                print("[skipping MACOSX env var setup]")

        # setup default spec
        if args["spec"] is None:
            if is_darwin():
                # Note: newer spack, for macOS we need to use `apple-clang`
                args["spec"] = "%apple-clang"
            else:
                args["spec"] = "%gcc"
            self.args["spec"] = "@{0}{1}".format(self.pkg_version,args["spec"])
        elif not args["spec"].startswith("@"):
            self.args["spec"] = "@{0}{1}".format(self.pkg_version,args["spec"])
        else:
            self.args["spec"] = "{0}".format(args["spec"])

        print("[spack spec: {0}]".format(self.args["spec"]))

        # Appends spec to package name (Example: 'magictestlib_cached@1.0.0%gcc')
        self.pkg_name_with_spec = "'{0}{1}'".format(self.pkg_name, self.args["spec"])

        # List of concretizer options not in all versions of spack
        # (to be checked if it exists after cloning spack)
        self.fresh_exists = False
        self.reuse_exists = False

    # Spack executable (will include environment -e option by default)
    def spack_exe(self, use_spack_env = True):
        exe = pjoin(self.dest_dir, "spack/bin/spack")

        # Add debug flags
        if self.args["spack_debug"]:
            exe = "{0} --debug --stacktrace".format(exe)

        # Run Spack with environment directory
        if use_spack_env:
            exe = "{0} -D {1}".format(exe, self.spack_env_directory)

        return exe

    # Returns version of Spack being used
    def spack_version(self):
        res, out = sexe('{0} --version'.format(self.spack_exe(use_spack_env=False)), ret_output=True)
        return out

    def check_concretizer_args(self):
        cmd = "{0} help install".format(self.spack_exe(use_spack_env=False))
        print("[Checking for concretizer options...]")
        res, out = sexe( cmd, ret_output = True)
        if "--fresh" in out:
            self.fresh_exists = True
            print("[--fresh exists.]")
        if "--reuse" in out:
            self.reuse_exists = True
            print("[--reuse exists.]")

    def add_concretizer_args(self, options):
        # reuse is now default in spack, if on and exists use that
        # otherwise use fresh if it exists
        if self.args["reuse"] and self.reuse_exists:
            options += "--reuse "
        elif self.fresh_exists:
            options += "--fresh "
        return options

    def print_spack_python_info(self):
        cmd = "{0} python -c \"import sys; print(sys.executable);\"".format(self.spack_exe(use_spack_env=False))
        res, out = sexe( cmd, ret_output = True)
        print("[spack python: {0}]".format(out.strip()))

    def append_path_to_packages_paths(self, path, errorOnNonexistant=True):
        path = pabs(path)
        if not os.path.exists(path):
            if errorOnNonexistant:
                print("[ERROR: Given path in 'spack_packages_path' does not exist: {0}]".format(path))
                sys.exit(-1)
            else:
                return
        self.packages_paths.append(path)


    def setup_paths_and_dirs(self):
        print("[setting up paths for environment]")
        # get the current working path

        UberEnv.setup_paths_and_dirs(self)

        # Next to uberenv.py (backwards compatibility)
        spack_configs_path = pabs(pjoin(self.uberenv_path,"spack_config"))

        # In project config file
        if "spack_configs_path" in self.project_args.keys():
            new_path = self.project_args["spack_configs_path"]
            if new_path is not None:
                spack_configs_path = pabs(new_path)
                if not os.path.isdir(spack_configs_path):
                    print("[ERROR: Given path in 'spack_configs_path' does not exist: {0}]".format(spack_configs_path))
                    sys.exit(-1)

        # Set spack_env_directory to absolute path and (if exists) check validity
        self.spack_env_name = self.args["spack_env_name"]
        self.spack_env_directory = pabs(os.path.join(self.dest_dir, self.spack_env_name))
        if os.path.exists(self.spack_env_directory) and not self.args["skip_setup_and_env"]:
            print("Removing old Spack Environment Directory: {0}".format(self.spack_env_directory))
            shutil.rmtree(self.spack_env_directory)

        # Setup path of Spack Environment file if not specified on command line
        # Check under spack_config_path -> detected platform -> spack.yaml/ .lock
        self.spack_env_file = self.args["spack_env_file"]
        if self.spack_env_file is None:
            # Check if platform is detected
            uberenv_plat = self.detect_platform()
            if not uberenv_plat is None:
                # Check if a path to an init file is located
                self.spack_env_file = pabs(pjoin(spack_configs_path, uberenv_plat))
                spack_env_yaml = pjoin(self.spack_env_file, "spack.yaml")
                spack_env_lock = pjoin(self.spack_env_file, "spack.lock")
                if os.path.exists(spack_env_yaml):
                    self.spack_env_file = spack_env_yaml
                elif os.path.exists(spack_env_lock):
                    self.spack_env_file = spack_env_lock
                else:
                    print("[WARNING: Could not find Spack Environment file (e.g. spack.yaml) under: {0}]".format(self.spack_env_file))
                    self.spack_env_file = None

        # Copy "defaults.yaml" and "versions.yaml" from configs dir, if they exist
        for _config_file in ("defaults.yaml", "versions.yaml"):
          _src = pjoin(spack_configs_path, _config_file)
          _dst = pabs(pjoin(self.spack_env_directory, "..", _config_file))
          print("[checking for '{0}' yaml file]".format(_src))
          if os.path.exists(_src):
            print("[copying '{0}' config file to {1}]".format(_config_file, _dst))
            shutil.copy(_src, _dst)

        # If you still could not find a spack.yaml, create one later on
        if self.spack_env_file is None:
            print("[No Spack Environment file found, so Uberenv will generate one. If you do not want this behavior, then supply a Spack Environment file in <spack_configs_path>/<platform>/ or specify one using the command line argument: --spack-env-file=/path/to/spack.yaml]")
            self.spack_setup_environment = True
        else:
            self.spack_env_file = pabs(self.spack_env_file)
            print("[Spack Environment file: {0}]".format(self.spack_env_file))

        # Find project level packages to override spack's internal packages
        if "spack_packages_path" in self.project_args.keys():
            # packages directories listed in project.json
            _paths = self.project_args["spack_packages_path"]
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

        if self.build_mode == "dev-build":
            self.pkg_src_dir = os.path.abspath(os.path.join(self.uberenv_path,self.pkg_src_dir))
            if not os.path.isdir(self.pkg_src_dir):
                print("[ERROR: package_source_dir '{0}' does not exist]".format(self.pkg_src_dir))
                sys.exit(-1)

    def find_spack_pkg_path_from_hash(self, pkg_name, pkg_hash):
        res, out = sexe("{0} find -p /{1}".format(self.spack_exe(), pkg_hash), ret_output = True)
        for l in out.split("\n"):
            # TODO: at least print a warning when several choices exist. This will
            # pick the first in the list.
            if l.startswith(pkg_name) and len(l.split()) > 1:
                return {"name": pkg_name, "path": l.split()[-1]}
        print("[ERROR: Failed to find package from hash named '{0}' with hash '{1}']".format(pkg_name, pkg_hash))
        sys.exit(-1)

    def find_spack_pkg_path(self, pkg_name, spec = ""):
        res, out = sexe("{0} find -p {1}".format(self.spack_exe(),self.pkg_name_with_spec), ret_output = True)
        for l in out.split("\n"):
            # TODO: at least print a warning when several choices exist. This will
            # pick the first in the list.
            if l.startswith(pkg_name) and len(l.split()) > 1:
                return {"name": pkg_name, "path": l.split()[-1]}
        print("[ERROR: Failed to find package from spec named '{0}' with spec '{1}']".format(pkg_name, spec))
        sys.exit(-1)

    def clone_repo(self):
        if not os.path.isdir(self.dest_spack):

            # compose clone command for the dest path, spack url and branch
            print("[info: cloning spack develop branch from github]")

            os.chdir(self.dest_dir)

            clone_args = ("-c http.sslVerify=false "
                          if self.args["ignore_ssl_errors"] else "")

            spack_url = self.project_args.get("spack_url", "https://github.com/spack/spack.git")
            spack_branch = self.project_args.get("spack_branch", "develop")

            clone_cmd =  "git {0} clone --single-branch --depth=1 -b {1} {2} spack".format(clone_args, spack_branch, spack_url)
            res = sexe(clone_cmd, echo=True)
            if res != 0:
                print("[ERROR: Git failed to clone Spack repository]")
                sys.exit(-1)

        if "spack_commit" in self.project_args:
            # optionally, check out a specific commit
            os.chdir(pjoin(self.dest_dir,"spack"))
            sha1 = self.project_args["spack_commit"]
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

        if self.args["repo_pull"]:
            # do a pull to make sure we have the latest
            os.chdir(pjoin(self.dest_dir,"spack"))
            sexe("git stash", echo=True)
            res = sexe("git pull", echo=True)
            if res != 0:
                #Usually untracked files that would be overwritten
                print("[ERROR: Git failed to pull]")
                sys.exit(-1)

        # Move destination of Spack builtin package repository if not included in Spack repo (pre-1.0)
        if not os.path.exists(pjoin(self.dest_spack, "var", "spack", "repos", "builtin")):
            builtin_repo = pjoin(self.dest_dir, "builtin_spack_packages_repo")
            print(f"[info: moving spack builtin package repository to {builtin_repo}]")
            spack_repo_set_cmd = f"{self.spack_exe(use_spack_env=False)} repo set --destination {builtin_repo} builtin"
            res = sexe(spack_repo_set_cmd, echo=True)
            if res != 0:
                print("[ERROR: Failed to set builtin package repository destination]")
                sys.exit(-1)


    def disable_spack_config_scopes(self):
        # disables all config scopes except "defaults", which we will
        # force our settings into
        spack_lib_config = pjoin(self.dest_spack,"lib","spack","spack","config.py")
        print("[disabling config scope (except defaults) in: {0}]".format(spack_lib_config))
        cfg_script = open(spack_lib_config).read()
        #
        # For newer versions of spack, we can use the SPACK_DISABLE_LOCAL_CONFIG
        # env var plumbing. We patch it to True to make a permanent change.
        #
        # Note: This path does not disable the 'site' config, but disabling 'user' config
        # is our primary goal.
        #
        spack_disable_env_stmt = 'disable_local_config = "SPACK_DISABLE_LOCAL_CONFIG" in os.environ'
        spack_disable_env_stmt_perm = "disable_local_config = True"
        if cfg_script.count(spack_disable_env_stmt) > 0:
            cfg_script = cfg_script.replace(spack_disable_env_stmt,
                                            spack_disable_env_stmt_perm)
        # path for older versions of spack
        elif cfg_script.count(spack_disable_env_stmt_perm) == 0:
            for cfg_scope_stmt in ["('system', os.path.join(spack.paths.system_etc_path, 'spack')),",
                                "('site', os.path.join(spack.paths.etc_path, 'spack')),",
                                "('user', spack.paths.user_config_path)"]:
                cfg_script = cfg_script.replace(cfg_scope_stmt,
                                                "#DISABLED BY UBERENV: " + cfg_scope_stmt)
        open(spack_lib_config,"w").write(cfg_script)

    def patch(self):
        # this is an opportunity to show spack python info post obtaining spack
        self.print_spack_python_info()

        # force spack to use only "defaults" config scope
        self.disable_spack_config_scopes()

        # setup clingo (unless specified not to)
        if "spack_setup_clingo" in self.project_args and self.project_args["spack_setup_clingo"] == False:
            print("[info: clingo will not be installed by uberenv]")
        else:
            self.setup_clingo()

        # Check which concretizer this version of Spack has
        self.check_concretizer_args()

    def create_spack_env(self):
        # Create Spack Environment
        print("[creating spack env]")
        if self.spack_env_file is None:
            self.spack_env_file = ""
        spack_create_cmd = "{0} env create -d {1} {2}".format(self.spack_exe(use_spack_env=False),
            self.spack_env_directory, self.spack_env_file)
        res = sexe(spack_create_cmd, echo=True)
        if res != 0:
            print("[ERROR: Failed to create Spack Environment]")
            sys.exit(-1)

        # Find pre-installed compilers and packages and stop uberenv.py
        if self.spack_setup_environment:
            # Finding compilers
            print("[finding compilers]")
            if self.spack_compiler_paths is None:
                spack_compiler_find_cmd = "{0} compiler find".format(self.spack_exe())
            else:
                spack_compiler_find_cmd = "{0} compiler find {1}".format(self.spack_exe(), self.spack_compiler_paths)
            res_compiler = sexe(spack_compiler_find_cmd, echo=True)
            if res_compiler != 0:
                print("[ERROR: Failed to setup Spack Environment]")
                sys.exit(-1)

            # Finding externals
            spack_external_find_cmd = "{0} external find --not-buildable".format(self.spack_exe())
            if self.spack_externals is None:
                print("[finding all packages Spack knows about]")
                spack_external_find_cmd = "{0} --all".format(spack_external_find_cmd)
            else:
                print("[finding packages from list]")
                spack_external_find_cmd = "{0} {1}".format(spack_external_find_cmd, self.spack_externals)
            res_external = sexe(spack_external_find_cmd, echo=True)
            if res_external != 0:
                print("[ERROR: Failed to setup Spack Environment]")
                sys.exit(-1)

            # Copy spack.yaml to where you called package source dir
            generated_spack_yaml = pjoin(self.spack_env_directory, "spack.yaml")
            copied_spack_yaml = pjoin(pabs(self.pkg_src_dir), "spack.yaml")
            print("[copying spack yaml file to {0}]".format(copied_spack_yaml))
            sexe("cp {0} {1}".format(generated_spack_yaml, copied_spack_yaml))

            print("[setup environment]")

        # For each package path (if there is a repo.yaml), add Spack repository to environment
        if len(self.packages_paths) > 0:
            for _base_path in self.packages_paths:
                spack_pkg_repo      = os.path.join(_base_path, "../")
                spack_pkg_repo_yaml = os.path.join(_base_path, "../repo.yaml")
                if os.path.isfile(os.path.join(spack_pkg_repo_yaml)):
                    print("[adding spack repo {0}]".format(spack_pkg_repo))
                    spack_repo_add_cmd = "{0} repo add {1}".format(self.spack_exe(), spack_pkg_repo)
                    sexe(spack_repo_add_cmd, echo=True)
                else:
                    print("[ERROR: No Spack repo.yaml detected in {0}]".format(spack_pkg_repo))
                    sys.exit(-1)

        # Add spack package
        print("[adding spack package]")
        spack_add_cmd = "{0} add {1}".format(self.spack_exe(),
            self.pkg_name_with_spec)
        sexe(spack_add_cmd, echo=True)

        # For dev-build, call develop
        if self.build_mode == "dev-build":
            print("[calling spack develop]")
            spack_develop_cmd = "{0} develop --no-clone --path={1} {2}".format(
                self.spack_exe(), self.pkg_src_dir, self.pkg_name_with_spec)
            sexe(spack_develop_cmd, echo=True)

    def concretize_spack_env(self):
        # Spack concretize
        print("[concretizing spack env]")
        spack_concretize_cmd = "{0} concretize ".format(self.spack_exe())
        spack_concretize_cmd = self.add_concretizer_args(spack_concretize_cmd)
        sexe(spack_concretize_cmd, echo=True)

    def clean_build(self):
        # clean out any spack cached stuff (except build stages, downloads, &
        # spack's bootstrapping software)
        cln_cmd = "{0} clean --misc-cache --failures --python-cache".format(self.spack_exe(use_spack_env=False))
        res = sexe(cln_cmd, echo=True)

        # check if we need to force uninstall of selected packages
        if self.args["spack_clean"]:
            if "spack_clean_packages" in self.project_args:
                for cln_pkg in self.project_args["spack_clean_packages"]:
                    if self.find_spack_pkg_path(cln_pkg) is not None:
                        unist_cmd = "{0} uninstall -f -y --all --dependents ".format(self.spack_exe()) + cln_pkg
                        res = sexe(unist_cmd, echo=True)

    def show_info(self):
        # print version of spack
        print("[spack version: {0}]".format(self.spack_version()))

        # print concretized spec with install info
        # default case prints install status and 32 characters hash

        options = ""
        options = self.add_concretizer_args(options)
        options += "--install-status --very-long"
        spec_cmd = "{0} spec {1}".format(self.spack_exe(), options)

        res, out = sexe(spec_cmd, ret_output=True, echo=True)
        print(out)

        # Check if spec is already installed and set spec_hash
        for line in out.split("\n"):
            # Example of matching line: ("status"  "hash"  "package"...)
            # [+]  hf3cubkgl74ryc3qwen73kl4yfh2ijgd  serac@develop%clang@10.0.0-apple~debug~devtools~glvis arch=darwin-mojave-x86_64
            if re.match(r"^(\[\+\]| - )  [a-z0-9]{32}  " + re.escape(self.pkg_name), line):
                self.spec_hash = line.split("  ")[1].lstrip()
                # if spec already installed
                if line.startswith("[+]"):
                    pkg_path = self.find_spack_pkg_path_from_hash(self.pkg_name,self.spec_hash)
                    install_path = pkg_path["path"]
                    # testing that the path exists is mandatory until Spack team fixes
                    # https://github.com/spack/spack/issues/16329
                    if os.path.isdir(install_path):
                        print("[Warning: {0} has already been installed in {1}]".format(self.pkg_name_with_spec,install_path))
                        print("[Warning: Uberenv will proceed using this directory]")
                        self.use_install = True

        return res


    def install(self):
        # use the uberenv package to trigger the right builds
        # and build an host-config.cmake file
        if not self.use_install:
            # create install command using appropriate flags
            install_cmd = self.spack_exe() + " "

            # spack flags
            if self.args["ignore_ssl_errors"]:
                install_cmd += "-k "

            # install flags
            install_cmd += "install "
            install_cmd = self.add_concretizer_args(install_cmd)
            if self.build_mode == "dev-build":
                install_cmd += "--keep-stage "
            if self.args["spack_allow_deprecated"]:
                install_cmd += "--deprecated "
            if self.pkg_final_phase:
                install_cmd += "-u {0} ".format(self.pkg_final_phase)
            if self.args["run_tests"]:
                install_cmd += "--test=root "
            if self.args["build_jobs"]:
                install_cmd += "-j {0} ".format(self.args["build_jobs"])

            res = sexe(install_cmd, echo=True)
            if res != 0:
                print("[ERROR: Failure of spack install]")
                return res

        # when using install or uberenv-pkg mode, create a symlink to the host config 
        if self.build_mode == "install" or \
           self.build_mode == "uberenv-pkg" \
           or self.use_install:
            # only create a symlink if you're completing all phases
            if self.pkg_final_phase == None or self.pkg_final_phase == "install":
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
                        hc_symlink_path = pjoin(self.dest_dir,hc_fname)
                        if os.path.islink(hc_symlink_path):
                            os.unlink(hc_symlink_path)
                        elif os.path.isfile(hc_symlink_path):
                            sexe("rm -f {0}".format(hc_symlink_path))
                        print("[symlinking host config file {0} to {1}]".format(hc_path,hc_symlink_path))
                        os.symlink(hc_path,hc_symlink_path)
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
            print("[ERROR: Unsupported build mode: {0}]".format(self.build_mode))
            return -1

    def get_mirror_path(self):
        mirror_path = self.args["mirror"]
        if not mirror_path:
            print("[ERROR: `--create-mirror` requires a mirror directory]")
            sys.exit(-1)
        return mirror_path

    def create_mirror(self):
        """
        Creates a spack mirror for pkg_name at mirror_path.
        """

        mirror_path = self.get_mirror_path()

        mirror_cmd = "{0} ".format(self.spack_exe())
        if self.args["ignore_ssl_errors"]:
            mirror_cmd += "-k "
        mirror_cmd += "mirror create -d {0} --dependencies {1}".format(
            mirror_path, self.pkg_name_with_spec)
        return sexe(mirror_cmd, echo=True)

    def find_spack_mirror(self, mirror_name):
        """
        Returns the path of a defaults scoped spack mirror with the
        given name, or None if no mirror exists.
        """
        res, out = sexe("{0} mirror list".format(self.spack_exe()), ret_output=True)
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
            sexe("{0} mirror remove --scope=defaults {1} ".format(self.spack_exe(), mirror_name),
                echo=True)
            existing_mirror_path = None
        if not existing_mirror_path:
            # Add if not already there
            sexe("{0} mirror add --scope=defaults {1} {2}".format(
                    self.spack_exe(), mirror_name, mirror_path), echo=True)
            print("[using mirror {0}]".format(mirror_path))

    def find_spack_upstream(self, upstream_name):
        """
        Returns the path of a defaults scoped spack upstream with the
        given name, or None if no upstream exists.
        """
        upstream_path = None

        res, out = sexe('{0} config get upstreams'.format(self.spack_exe()), ret_output=True)
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
        upstream_path = self.args["upstream"]
        if not upstream_path:
            print("[ERROR: `--create-upstream` requires a upstream directory]")
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

    def setup_clingo(self):
        """
        Attempts to install the clingo answer set programming library via Spack
        if it is not already available as a Python module
        """
        if not have_internet():
            print("[WARNING: No internet detected. Skipping setting up clingo.]")
            return

        res = sexe('{0} bootstrap now'.format(self.spack_exe(use_spack_env = False)), echo=True)
        if res != 0:
            print("[ERROR: 'spack bootstrap now' failed with returncode {0}]".format(res))
            sys.exit(-1)

        res = sexe('{0} bootstrap status'.format(self.spack_exe(use_spack_env = False)), echo=True)
        if res != 0:
            print("[ERROR: 'spack bootstrap status' failed with returncode {0}]".format(res))
            sys.exit(-1)


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
    args, extra_args = parse_args()

    # project options
    args["project_json"] = find_project_config(args)

    # Initialize the environment -- use vcpkg on windows, spack otherwise
    env = SpackEnv(args, extra_args) if not is_windows() else VcpkgEnv(args, extra_args)

    # Setup the necessary paths and directories
    env.setup_paths_and_dirs()

    # Go to package manager's destination
    os.chdir(env.dest_dir)

    # Setup package manager
    if not args["skip_setup"] and not args["skip_setup_and_env"]:
        # Clone the package manager
        env.clone_repo()

        # Patch the package manager, as necessary
        env.patch()

        # Clean the build
        env.clean_build()

        # Allow to end uberenv after Spack is ready
        if args["setup_only"]:

            # Use Spack upstream
            if not is_windows() and args["upstream"] is not None:
                env.use_spack_upstream()

            return 0

    # Create Spack Environment and setup Spack package repos
    if not is_windows() and not args["skip_setup_and_env"]:
        env.create_spack_env()

        # Allow to end uberenv after Spack environment is ready
        if args["setup_and_env_only"]:
            return 0

    ###########################################################
    # We now have an instance of our package manager configured,
    # now we need it to build our TPLs. At this point, there are
    # two possible next steps:
    #
    # *) create a mirror of the packages
    #   OR
    # *) build
    #
    ###########################################################
    if args["create_mirror"]:
        return env.create_mirror()
    else:
        # Add mirror
        if args["mirror"] is not None:
            env.use_mirror()

        # Use Spack upstream
        if not is_windows() and args["upstream"] is not None:
            env.use_spack_upstream()

        # Concretize the spack environment
        if not is_windows():
            env.concretize_spack_env()

        # Show the spec for what will be built
        env.show_info()

        # Install
        return env.install()

if __name__ == "__main__":
    sys.exit(main())
