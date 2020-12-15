# Uberenv Software Release Notes

Notes describing significant changes in each Uberenv release are documented
in this file.

The format of this file is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/).

The Uberenv project release numbers follow [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## Unreleased

### Added
- Allow projects to force specifying `--prefix` on command line via new project option:
  `force_commandline_prefix`.  This is useful when the default `uberenv_libs` can not exist
  inside of your project's source repository.

### Changed
- Added ability to have multiple packages directories that will get copied into spack on top of
  each other via project configuration option: `spack_packages_path`
- Pretty print various options to screen for readability
- Allow `.uberenv_config.json` to live at the same level as `uberenv.py`
- No longer removes symlinks when using the directory of `uberenv.py`
- Reduce Spack's git history to a bare minimum

### Fixed
