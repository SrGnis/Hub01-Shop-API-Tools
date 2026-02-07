# Hub01 Publishing Tool

A utility script to automate version publishing for Hub01 Shop. It handles manifest creation from Git repositories and uploading to the Hub01 API.

## Requirements

- Python 3.6+
- `hub01_client` library
- `GitPython`
- `PyGithub`

```bash
pip install gitpython PyGithub hub01_client
```

## Usage

The script is a CLI tool with a single entry point `publish.py`.

```bash
python3 publish.py [INPUT] [OPTIONS]
```

### Arguments

**Positional:**

- `INPUT`: Path to a local git repository OR a URL to a remote git repository.

**General Options:**

- `--subfolder PATH`: Path to the project subfolder within the repository (default: root).
- `--mode {manifest,upload,both}`: Action to perform (default: `both`).

**Version Selection:**

- `--commit HASH`: Checkout a specific commit hash.
- `--tag TAG`: Checkout a specific git tag.
  _(Default: Uses `HEAD` of the repository)_

**Manifest Options:**

- `--release-type {release,beta,alpha}`: Type of the release (default: `release`).
- `--tags "tag1,tag2"`: Comma-separated list of tags.
- `--github-token TOKEN`: GitHub API token for prevent rate limiting when fetching release info.
- `--manifest-path PATH`: Output path for `manifest.json` (file or directory). Defaults to current working directory.

**Upload Options:**

- `--project-slug SLUG`: The project slug on Hub01.
- `--api-url URL`: The Hub01 API URL.
- `--api-token TOKEN`: Your Hub01 API token.
- `--overwrite`: Overwrite the version if it already exists.

## Examples

### 1. Full Publish from Remote URL

Clones the repo, creates a manifest, zips the subfolder, and uploads it.

```bash
python3 publish.py https://github.com/User/MyRepo.git \
  --subfolder "src/mod" \
  --project-slug "my-mod" \
  --api-url "https://hub01-shop.srgnis.com/api" \
  --api-token "MY_TOKEN"
```

### 2. Create Manifest Only (Local Repo)

Generates `manifest.json` in the current directory based on a local repo.

```bash
python3 publish.py /path/to/local/repo \
  --mode manifest \
  --subfolder "mod_data" \
  --manifest-path ./output/
```

### 3. Upload Only (Existing Manifest)

Uploads a project using an existing `manifest.json`.

```bash
python3 publish.py /path/to/local/repo \
  --mode upload \
  --subfolder "mod_data" \
  --manifest-path ./output/manifest.json \
  --project-slug "my-mod" \
  --api-url "https://hub01-shop.srgnis.com/api" \
  --api-token "MY_TOKEN"
```

### 4. Publish Specific Version

Checkout a specific tag before publishing.

```bash
python3 publish.py https://github.com/User/MyRepo.git \
  --tag "v1.0.0" \
  --project-slug "my-mod" \
  ...
```

## Manifest Generation Logic

The script determines the version number in the following priority:

1. `modinfo.json` `version` field (if present in the subfolder).
2. Git Tag pointing to the commit (matching version regex).
3. Commit Date (fallback format: `YYYY.MM.DD.HHMMSS`).

It also attempts to fetch the release name and changelog from GitHub Releases if a GitHub token is provided.
