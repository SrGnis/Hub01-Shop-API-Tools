#!/usr/bin/env python3
import os
import json
import argparse
import re
import shutil
import tempfile
import zipfile
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

# Dependencies: gitpython, pygithub, hub01_client
try:
    import git
    from github import Github, GithubException
    from hub01_client.client import HubClient
    from hub01_client.exceptions import HubAPIException
except ImportError as e:
    print(f"Error: Missing dependency: {e}")
    print("Please install: pip install gitpython PyGithub")
    # hub01_client check is separate or assumed present
    if 'hub01_client' in str(e):
        print("Please ensure hub01_client is installed.")
    exit(1)

def sanitize_version(version: str) -> str:
    """
    Sanitizes a version string to be valid for Hub01 Shop.
    """
    return re.sub(r'[^a-zA-Z0-9_.+-]', '-', version)

def setup_repo(path_or_url: str, temp_dir: Optional[str] = None) -> Tuple[git.Repo, str]:
    """
    Sets up the git repository.
    If path_or_url is a URL, clones to temp_dir.
    If path_or_url is a path, opens the repo.
    Returns (Repo object, root_path_of_repo).
    """
    if path_or_url.startswith(('http://', 'https://', 'git@', 'ssh://')):
        if not temp_dir:
            raise ValueError("Temp directory required for cloning")
        print(f"Cloning {path_or_url} to {temp_dir}...")
        repo = git.Repo.clone_from(path_or_url, temp_dir)
        return repo, temp_dir
    else:
        path = os.path.abspath(path_or_url)
        if not os.path.exists(path):
             raise ValueError(f"Path does not exist: {path}")
        
        try:
            repo = git.Repo(path, search_parent_directories=True)
            return repo, repo.working_dir
        except git.InvalidGitRepositoryError:
            raise ValueError(f"Not a git repository: {path}")

def get_github_release_info(repo_url: str, token: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Attempts to fetch release info from GitHub using PyGithub.
    """
    if not token:
        return None

    # Extract info from URL
    # Supports: https://github.com/owner/repo.git, git@github.com:owner/repo.git, etc.
    # Simple regex to get owner/repo
    match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', repo_url)
    if not match:
        return None
    
    owner, repo_name = match.groups()
    
    try:
        g = Github(token)
        gh_repo = g.get_repo(f"{owner}/{repo_name}")
        release = gh_repo.get_latest_release()
        return {
            'name': release.title, # PyGithub uses 'title' for name? release.title is typically the name
            'body': release.body,
            'tag_name': release.tag_name
        }
    except GithubException as e:
        print(f"Warning: GitHub API error: {e}")
        return None
    except Exception as e:
         print(f"Warning: Failed to fetch GitHub release info: {e}")
         return None

def extract_version(repo_root: str, subfolder: str, head_commit: git.Commit, version_regex: str = r'^[a-zA-Z0-9_.+-]+$') -> str:
    """
    Determines version.
    1. modinfo.json in subfolder
    2. git tag on HEAD
    3. commit date
    """
    full_path = os.path.join(repo_root, subfolder)
    
    # 1. modinfo.json
    modinfo_path = os.path.join(full_path, 'modinfo.json')
    if os.path.exists(modinfo_path):
        try:
            with open(modinfo_path, 'r') as f:
                data = json.load(f)
                if 'version' in data:
                    raw_ver = str(data['version'])
                    if re.match(version_regex, raw_ver):
                        return raw_ver
                    else:
                        return sanitize_version(raw_ver)
        except Exception:
            pass

    # 2. Git tag
    # Check tags pointing to this commit
    # repo.tags is list of tags. We need to check if any tag.commit == head_commit
    # Efficient way:
    tags = [tag for tag in head_commit.repo.tags if tag.commit == head_commit]
    for tag in tags:
        name = tag.name.lstrip('v')
        if re.match(version_regex, name):
            return name
        else:
            return sanitize_version(name)

    # 3. Commit Date
    # commit.committed_datetime is timezone-aware
    dt = head_commit.committed_datetime
    return dt.strftime('%Y.%m.%d.%H%M')

def create_manifest(args, repo: git.Repo, repo_root: str):
    print(f"Generating manifest...")

    # Checkout specific commit or tag if requested
    if args.commit:
        print(f"Checking out commit {args.commit}...")
        repo.git.checkout(args.commit)
    elif args.tag:
        print(f"Checking out tag {args.tag}...")
        repo.git.checkout(args.tag)
    
    # Get the commit object (HEAD after checkout)
    head = repo.head.commit
    
    # Release Date = Commit Date
    release_date = head.committed_datetime.isoformat()
    
    # Git Info
    remote_url = ""
    try:
        remote_url = repo.remotes.origin.url
    except AttributeError:
        pass
        
    # Version
    version = extract_version(repo_root, args.subfolder, head)
    print(f"Detected version: {version}")

    # GitHub Info
    github_release = None
    if remote_url and args.github_token:
        github_release = get_github_release_info(remote_url, args.github_token)

    # Manifest
    manifest = {
        'version': version,
        'repository_url': remote_url,
        'commit': head.hexsha,
        'release_type': args.release_type,
        'release_date': release_date, # Add this to manifest so upload can use it
        'subfolder': args.subfolder,
        'tags': args.tags.split(',') if args.tags else [],
        'name': github_release['name'] if github_release else version,
        'changelog': github_release['body'] if github_release else str(head.message).strip()
    }
    
    # Determine output path
    if args.manifest_path:
        # Check if dir
        if os.path.isdir(args.manifest_path) or args.manifest_path.endswith(os.sep):
             output_path = os.path.join(args.manifest_path, 'manifest.json')
        else:
             output_path = args.manifest_path
    else:
        # Default to CWD
        output_path = os.path.join(os.getcwd(), 'manifest.json')
    
    # Ensure dir exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(output_path, 'w') as f:
        json.dump(manifest, f, indent=4)
        
    print(f"Manifest written to {output_path}")
    return manifest, output_path

def pack_and_upload(args, manifest, project_dir):
    if not args.project_slug or not args.api_url or not args.api_token:
        print("Upload skipped: Missing required upload arguments (--project-slug, --api-url, --api-token)")
        return

    client = HubClient(args.api_url, args.api_token)
    
    print(f"Preparing upload for {args.project_slug} version {manifest['version']}...")
    
    # Zip
    zip_name = f"{manifest['name']}.zip"
    zip_name = "".join([c for c in zip_name if c.isalpha() or c.isdigit() or c in (' ','.','_','-')]).rstrip()
    zip_path = os.path.join(tempfile.gettempdir(), zip_name)
    
    print(f"Zipping {project_dir} to {zip_path}...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_dir):
            if '.git' in dirs:
                dirs.remove('.git')
            for file in files:
                if file == 'manifest.json': continue
                abs_file = os.path.join(root, file)
                rel_path = os.path.relpath(abs_file, project_dir)
                zipf.write(abs_file, rel_path)

    # Upload
    try:
        # Check exists
        try:
             existing = client.versions.get(args.project_slug, manifest['version'])
             if existing:
                 if not args.overwrite:
                     print(f"Version {manifest['version']} exists. Skipping. (Use --overwrite to force)")
                     return
                 print(f"Version {manifest['version']} exists. Overwriting...")
        except BaseException:
             pass # Not found
             
        with open(zip_path, 'rb') as f:
            print("Uploading...")
            client.versions.create(
                slug=args.project_slug,
                name=manifest['name'],
                version=manifest['version'],
                release_type=manifest['release_type'],
                release_date=manifest.get('release_date', datetime.now().isoformat()),
                files=[f], 
                changelog=manifest['changelog'],
                tags=manifest.get('tags', [])
            )
            print("Upload successful!")
            
    except HubAPIException as e:
         print(f"Upload failed: {e}")
    finally:
         if os.path.exists(zip_path):
             os.remove(zip_path)

def main():
    parser = argparse.ArgumentParser(description="Hub01 Publishing Tool")
    
    # Input args
    parser.add_argument('input', help='Repo path or URL')
    parser.add_argument('--subfolder', default='.', help='Project subfolder within repo')
    
    # Version selection (mutually exclusive)
    g = parser.add_mutually_exclusive_group()
    g.add_argument('--commit', help='Commit hash to checkout')
    g.add_argument('--tag', help='Tag to checkout')
    
    # Manifest args
    parser.add_argument('--release-type', default='release', choices=['release', 'beta', 'alpha'])
    parser.add_argument('--tags', help='Comma-separated tags')
    parser.add_argument('--github-token', default=os.environ.get('GITHUB_TOKEN'), help='GitHub Token')
    parser.add_argument('--manifest-path', help='Output path for manifest.json (file or dir). Defaults to CWD.')
    
    # Upload args
    parser.add_argument('--project-slug', help='Hub01 Project Slug')
    parser.add_argument('--api-url', help='Hub01 API URL')
    parser.add_argument('--api-token', help='Hub01 API Token')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing version')
    
    # Mode
    parser.add_argument('--mode', choices=['manifest', 'upload', 'both'], default='both', help='Action to perform')

    args = parser.parse_args()

    # Temp dir context
    temp_dir = tempfile.mkdtemp() if args.input.startswith(('http', 'git@', 'ssh')) else None
    
    try:
        repo, repo_root = setup_repo(args.input, temp_dir)
        project_dir = os.path.join(repo_root, args.subfolder)
        if not os.path.exists(project_dir):
             raise ValueError(f"Project directory not found: {project_dir}")

        manifest = None
        
        if args.mode in ['manifest', 'both']:
            manifest, manifest_path = create_manifest(args, repo, repo_root)
        
        if args.mode in ['upload', 'both']:
            # If we didn't create manifest in this run, load it
            if not manifest:
                 # Determine where to check
                 if args.manifest_path:
                      if os.path.isdir(args.manifest_path) or args.manifest_path.endswith(os.sep):
                           check_path = os.path.join(args.manifest_path, 'manifest.json')
                      else:
                           check_path = args.manifest_path
                 else:
                      check_path = os.path.join(os.getcwd(), 'manifest.json')

                 if os.path.exists(check_path):
                     with open(check_path, 'r') as f:
                         manifest = json.load(f)
                     
                     # Update project_dir if subfolder is in manifest
                     if 'subfolder' in manifest:
                         print(f"Using subfolder from manifest: {manifest['subfolder']}")
                         project_dir = os.path.join(repo_root, manifest['subfolder'])
                         if not os.path.exists(project_dir):
                             raise ValueError(f"Project directory from manifest not found: {project_dir}")
                 else:
                     print(f"Error: manifest.json not found at {check_path}.")
                     return
            
            pack_and_upload(args, manifest, project_dir)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == '__main__':
    main()
