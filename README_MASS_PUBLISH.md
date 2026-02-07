# Mass Publishing Tool for Hub01

An interactive batch publishing script that automates publishing multiple Git tags to Hub01 Shop at once. This script uses regex pattern matching to select tags and provides confirmation steps before generating manifests and uploading.

## Requirements

Same as `publish.py`:
- Python 3.6+
- `hub01_client` library
- `GitPython`
- `PyGithub`

```bash
pip install gitpython PyGithub hub01_client
```

## How It Works

The script operates in three interactive phases:

### Phase 1: Tag Selection
1. Scans all Git tags in the repository
2. Matches tags against the provided regex pattern
3. Displays matching tags and asks for user confirmation

### Phase 2: Manifest Generation
1. For each confirmed tag, calls `publish.py` to generate a manifest
2. Stores all manifests in a temporary directory (or specified location)
3. Displays all generated manifests
4. Asks for user confirmation before proceeding

### Phase 3: Upload
1. For each manifest, calls `publish.py` to upload the version
2. Reports success/failure for each upload
3. Provides a summary at the end

## Usage

```bash
python3 mass_publish.py [INPUT] --pattern REGEX [OPTIONS]
```

### Required Arguments

- `INPUT`: Path to a local git repository OR a URL to a remote git repository
- `--pattern REGEX`: Regular expression pattern to match Git tags
- `--project-slug SLUG`: The project slug on Hub01
- `--api-url URL`: The Hub01 API URL
- `--api-token TOKEN`: Your Hub01 API token

### Optional Arguments

**General Options:**
- `--subfolder PATH`: Path to the project subfolder within the repository (default: root)

**Manifest Options:**
- `--release-type {release,beta,alpha}`: Type of the release (default: `release`)
- `--tags "tag1,tag2"`: Comma-separated list of tags to add to all versions
- `--github-token TOKEN`: GitHub API token for prevent rate limiting when fetching release info (can also use `GITHUB_TOKEN` env var)
- `--manifest-dir DIR`: Directory to store manifests (default: temporary directory)

**Upload Options:**
- `--overwrite`: Overwrite versions if they already exist

## Examples

### 1. Publish All v1.x Releases

Publish all tags matching the pattern `v1.*`:

```bash
python3 mass_publish.py /path/to/repo \
  --pattern "^v1\\..*" \
  --project-slug "my-project" \
  --api-url "https://hub01-shop.srgnis.com/api" \
  --api-token "YOUR_TOKEN"
```

### 2. Publish Release Tags from Remote Repo

Clone a remote repo and publish all tags starting with "release-":

```bash
python3 mass_publish.py https://github.com/user/repo.git \
  --pattern "^release-" \
  --subfolder "src/mod" \
  --release-type "release" \
  --project-slug "my-mod" \
  --api-url "https://hub01-shop.srgnis.com/api" \
  --api-token "YOUR_TOKEN"
```

### 3. Publish Beta Versions with Overwrite

Publish all beta tags and overwrite if they already exist:

```bash
python3 mass_publish.py /path/to/repo \
  --pattern "beta" \
  --release-type "beta" \
  --overwrite \
  --project-slug "my-project" \
  --api-url "https://hub01-shop.srgnis.com/api" \
  --api-token "YOUR_TOKEN"
```

### 4. Publish Specific Version Range

Publish all v2.x.x versions:

```bash
python3 mass_publish.py /path/to/repo \
  --pattern "^v2\\.[0-9]+\\.[0-9]+$" \
  --project-slug "my-project" \
  --api-url "https://hub01-shop.srgnis.com/api" \
  --api-token "YOUR_TOKEN"
```

### 5. Keep Manifests for Review

Store manifests in a specific directory for later review:

```bash
python3 mass_publish.py /path/to/repo \
  --pattern "^v.*" \
  --manifest-dir "./manifests" \
  --project-slug "my-project" \
  --api-url "https://hub01-shop.srgnis.com/api" \
  --api-token "YOUR_TOKEN"
```

## Regex Pattern Examples

| Pattern | Matches |
|---------|---------|
| `^v.*` | All tags starting with "v" (v1.0.0, v2.3.1, etc.) |
| `^v1\\..*` | All v1.x versions (v1.0.0, v1.2.3, etc.) |
| `^v[0-9]+\\.[0-9]+\\.[0-9]+$` | Semantic versions only (v1.0.0, v2.1.3) |
| `beta` | Any tag containing "beta" |
| `^release-` | Tags starting with "release-" |
| `.*` | All tags (use with caution!) |

## Interactive Flow

When you run the script, you'll see:

```
Setting up repository...
Scanning tags with pattern: ^v1\..*

Found 5 matching tag(s):
------------------------------------------------------------
  1. v1.0.0
  2. v1.0.1
  3. v1.1.0
  4. v1.2.0
  5. v1.2.1
------------------------------------------------------------

Proceed with publishing these 5 tag(s)? [y/N]: y

Generating manifests in /tmp/mass_publish_xyz...
============================================================

Processing tag: v1.0.0
...

Proceed with uploading 5 version(s)? [y/N]: y

Uploading 5 version(s)...
============================================================
...
Upload Summary:
  Successful: 5/5

Mass publish complete!
```

## Notes

- The script will automatically clean up temporary directories when finished
- If you abort at any confirmation step, no changes will be made
- Each tag is processed independently - if one fails, others will continue
- Manifests are generated in subdirectories named after each tag

## Troubleshooting

**Q: No tags matched my pattern**
- Check your regex syntax - remember to escape special characters (e.g., `\\.` for literal dots)
- Use `git tag` to list all available tags in your repository

**Q: Script fails during manifest generation**
- Check that `publish.py` is in the same directory as `mass_publish.py`
- Ensure all dependencies are installed
- Check that the subfolder path is correct

**Q: Upload fails for some tags**
- Check if versions already exist (use `--overwrite` if needed)
- Verify API credentials and permissions
- Review individual error messages in the output

## Environment Variables

- `GITHUB_TOKEN`: GitHub API token (alternative to `--github-token`)
