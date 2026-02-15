# Hub01 API Tools

A collection of Python tools for publishing game mods and projects to [Hub01 Shop](https://hub01.shop).

## Overview

This repository contains two publishing utilities, check their individual documentation:

| Tool                                        | Description                                                                             |
| ------------------------------------------- | --------------------------------------------------------------------------------------- |
| [`publish.py`](README_SCRIPT.md)            | Single version publishing tool - creates manifests and uploads individual releases      |
| [`mass_publish.py`](README_MASS_PUBLISH.md) | Batch publishing tool - publishes multiple Git tags at once with regex pattern matching |

## Features

- **Git Integration**: Extract version info from Git tags, commits, or `modinfo.json`
- **Manifest Generation**: Automatically create version manifests with metadata
- **GitHub Integration**: Fetch release names and changelogs from GitHub Releases
- **Batch Operations**: Publish multiple versions simultaneously with pattern matching
- **Flexible Input**: Support for local Git repositories or remote URLs
- **Subfolder Support**: Publish specific subdirectories within a monorepo

## Requirements

- Python 3.6+
- `gitpython`
- `PyGithub`
- `hub01_client`

```bash
pip install gitpython PyGithub hub01_client
```

## Quick Start

### Single Version Publish

```bash
python3 publish.py /path/to/repo \
  --subfolder "src/mod" \
  --project-slug "my-mod" \
  --api-url "https://hub01-shop.srgnis.com/api" \
  --api-token "YOUR_TOKEN"
```

### Batch Publish Multiple Tags

```bash
python3 mass_publish.py /path/to/repo \
  --pattern "^v1\\..*" \
  --project-slug "my-mod" \
  --api-url "https://hub01-shop.srgnis.com/api" \
  --api-token "YOUR_TOKEN"
```

## Documentation

- [Publishing Tool Guide](README_SCRIPT.md) - Detailed documentation for `publish.py`
- [Mass Publishing Guide](README_MASS_PUBLISH.md) - Detailed documentation for `mass_publish.py`

## CI/CD Integration

### GitHub Actions

Automatically publish to Hub01 when creating Git tags using GitHub Actions you can adapt the example workflow that is provided in this repo: [publish-to-hub01.yml](publish-to-hub01.yml).

This workflow will:

1. Run when a tag starting with `v` is pushed
2. Fetch the latest version of `publish.py` from this repository
3. Install required dependencies
4. Publish the project to Hub01 Shop using the provided configuration.

**Setup:**

1. Create the workflow file at `.github/workflows/publish-to-hub01.yml`
2. Add `HUB01_API_TOKEN` as a GitHub secret
3. Push a tag starting with `v` (e.g., `v1.0.0`) to trigger publishing

## License

MIT License
