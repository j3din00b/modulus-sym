<!-- markdownlint-disable MD024 -->
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

### Added

- Added a CHANGELOG.md

### Changed

### Deprecated

### Removed

- Accompanying licenses (will provide in the Modulus docker image).

### Fixed

- Arch `from_config` bug for literal params.
- Fixed fused SiLU activation test.
- Update `np.bool` to `np.bool_`.

### Security

### Dependencies

- Updated the base container to latest PyTorch base container which is based on torch 2.0
- Container now supports CUDA 12, Python 3.10
- Updated symengine to >=0.10.0 and vtk to >=9.2.6

## [1.0.0] - 2023-05-08

### Added

- Initial public release.