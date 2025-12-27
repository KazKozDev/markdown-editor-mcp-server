# Release Instructions

This document describes how to publish a new release of the Markdown Editor MCP Server.

## Prerequisites

1. **PyPI Account**: Create an account at https://pypi.org
2. **PyPI API Token**:
   - Go to https://pypi.org/manage/account/token/
   - Click "Add API token"
   - Set scope to "Entire account" (or specific to this project after first release)
   - Copy the token (starts with `pypi-`)

3. **GitHub Secret**:
   - Go to your GitHub repository settings
   - Navigate to Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `PYPI_API_TOKEN`
   - Value: Paste your PyPI token
   - Click "Add secret"

## Automated Release Process

Once the PyPI token is configured as a GitHub secret, releases are automated:

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md** with release notes
3. **Commit and push** changes
4. **Create a GitHub Release**:
   - Go to https://github.com/KazKozDev/markdown-editor-mcp-server/releases/new
   - Choose or create a tag (e.g., `v0.1.0`)
   - Fill in release title and description
   - Click "Publish release"

5. **GitHub Actions automatically**:
   - Builds the package
   - Publishes to PyPI
   - Users can install with: `pip install markdown-editor-mcp-server`

## Manual Release (if needed)

If you need to publish manually:

```bash
# Build the package
python3 -m build

# Upload to PyPI
python3 -m twine upload dist/* -u __token__ -p YOUR_PYPI_TOKEN
```

## Version Guidelines

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality
- **PATCH** version for backwards-compatible bug fixes

## First Release Checklist

- [x] Package built successfully
- [x] GitHub Actions workflow configured
- [ ] PyPI API token added to GitHub secrets
- [ ] GitHub release created
- [ ] Package published to PyPI
- [ ] Installation tested: `pip install markdown-editor-mcp-server`
