# How to Release SQLAlchemy-Continuum

This document outlines the process for creating a new release of SQLAlchemy-Continuum.

## Prerequisites

- Access to the GitHub repository with push permissions
- PyPI account with API token for the project
- `uv` package manager installed
- `gh` CLI tool installed (optional, for GitHub releases)

## Release Process

### 1. Prepare the Release

1. **Update CHANGES.rst**
   - Move items from "Unreleased changes" section to a new version section
   - Follow the existing format: `X.Y.Z (YYYY-MM-DD)`
   - Add a new "Unreleased changes" section with `- TODO`

2. **Update version in pyproject.toml**
   ```bash
   # Edit pyproject.toml and update the version field
   version = "X.Y.Z"
   ```

3. **Update version in __init__.py**
   ```bash
   # Edit sqlalchemy_continuum/__init__.py and update the __version__ field
   __version__ = 'X.Y.Z'
   ```

4. **Commit the changes**
   ```bash
   git add CHANGES.rst pyproject.toml sqlalchemy_continuum/__init__.py
   git commit -m "Bump version to X.Y.Z"
   git push origin main
   ```

### 2. Create Git Tag

```bash
git tag -a X.Y.Z -m "Release version X.Y.Z"
git push origin X.Y.Z
```

### 3. Build and Publish to PyPI

1. **Build the package**
   ```bash
   uv build
   ```

2. **Publish to PyPI**
   ```bash
   uv publish --token pypi-your-api-token-here
   ```

   Alternatively, set the token as an environment variable:
   ```bash
   export UV_PUBLISH_TOKEN="pypi-your-api-token-here"
   uv publish
   ```

### 4. Create GitHub Release (Optional)

```bash
gh release create X.Y.Z --title "X.Y.Z" --notes-from-tag
```

Or create the release manually on GitHub using the tag.

## PyPI API Token Setup

1. Go to https://pypi.org/manage/account/token/
2. Create a new API token for the project
3. Copy the token (starts with `pypi-`)
4. Store it securely - you'll need it for publishing

## Version Numbering

This project follows [Semantic Versioning](https://semver.org/):
- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes