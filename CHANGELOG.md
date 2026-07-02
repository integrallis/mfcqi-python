# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.0.6] - 2026-07-01

### Breaking Changes
- Rename the installed CLI from `mfcqi` to `mfcqi-py`
- Move the project to `integrallis/mfcqi-python`

### Added
- Add bounded parallel metric evaluation via `--parallelism` or `MFCQI_PARALLELISM`
- Publish a runnable CLI container image to GitHub Container Registry
- Add the GitHub Pages documentation site

### Fixed
- Update CI and release validation to invoke the renamed Python CLI
