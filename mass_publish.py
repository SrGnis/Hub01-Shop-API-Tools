#!/usr/bin/env python3
import os
import sys
import json
import argparse
import re
import subprocess
import tempfile
import shutil
from typing import List, Dict, Any
from pathlib import Path

# Dependencies: gitpython, pygithub, hub01_client
try:
    import git
except ImportError as e:
    print(f"Error: Missing dependency: {e}")
    print("Please install: pip install gitpython")
    exit(1)


def get_matching_tags(repo: git.Repo, pattern: str) -> List[git.TagReference]:
    """
    Get all tags that match the given regex pattern.
    
    Args:
        repo: GitPython Repo object
        pattern: Regex pattern to match tags
        
    Returns:
        List of matching tag objects
    """
    try:
        regex = re.compile(pattern)
    except re.error as e:
        print(f"Error: Invalid regex pattern: {e}")
        return []
    
    matching_tags = []
    for tag in repo.tags:
        if regex.search(tag.name):
            matching_tags.append(tag)
    
    return matching_tags


def confirm_tags(tags: List[git.TagReference]) -> bool:
    """
    Display tags and ask for user confirmation.
    
    Args:
        tags: List of tag objects
        
    Returns:
        True if user confirms, False otherwise
    """
    if not tags:
        print("No tags matched the pattern.")
        return False
    
    print(f"\nFound {len(tags)} matching tag(s):")
    print("-" * 60)
    for i, tag in enumerate(tags, 1):
        print(f"{i:3}. {tag.name}")
    print("-" * 60)
    
    while True:
        response = input(f"\nProceed with publishing these {len(tags)} tag(s)? [y/N]: ").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no', '']:
            return False
        else:
            print("Please enter 'y' or 'n'")


def generate_manifests(args, tags: List[git.TagReference], manifest_dir: str) -> Dict[str, str]:
    """
    Generate manifests for all tags using publish.py script.
    
    Args:
        args: Command line arguments
        tags: List of tag objects
        manifest_dir: Directory to store manifests
        
    Returns:
        Dictionary mapping tag names to manifest file paths
    """
    manifests = {}
    publish_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'publish.py')
    
    if not os.path.exists(publish_script):
        print(f"Error: publish.py not found at {publish_script}")
        return manifests
    
    print(f"\nGenerating manifests in {manifest_dir}...")
    print("=" * 60)
    
    for tag in tags:
        tag_name = tag.name
        print(f"\nProcessing tag: {tag_name}")
        
        # Create subfolder for this tag's manifest
        tag_manifest_dir = os.path.join(manifest_dir, tag_name.replace('/', '_'))
        os.makedirs(tag_manifest_dir, exist_ok=True)
        manifest_path = os.path.join(tag_manifest_dir, 'manifest.json')
        
        # Build command to call publish.py
        cmd = [
            sys.executable,
            publish_script,
            args.input,
            '--mode', 'manifest',
            '--tag', tag_name,
            '--subfolder', args.subfolder,
            '--release-type', args.release_type,
            '--manifest-path', manifest_path
        ]
        
        # Add optional arguments
        if args.tags:
            cmd.extend(['--tags', args.tags])
        if args.github_token:
            cmd.extend(['--github-token', args.github_token])
        
        # Execute
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            manifests[tag_name] = manifest_path
        except subprocess.CalledProcessError as e:
            print(f"Error generating manifest for {tag_name}:")
            print(e.stdout)
            print(e.stderr, file=sys.stderr)
            print(f"Skipping tag {tag_name}")
    
    print("=" * 60)
    print(f"Generated {len(manifests)} manifest(s)")
    return manifests


def display_manifests_for_review(manifests: Dict[str, str]) -> bool:
    """
    Display manifests for user review using pydoc pager or fallback.
    
    Args:
        manifests: Dictionary mapping tag names to manifest paths
        
    Returns:
        True if user confirms, False otherwise
    """
    if not manifests:
        print("No manifests to review.")
        return False
    
    # Try to use pydoc pager
    try:
        import pydoc
        
        # Build content to display
        content = []
        content.append("=" * 70)
        content.append("MANIFEST REVIEW")
        content.append("=" * 70)
        content.append("")
        
        for tag_name, manifest_path in manifests.items():
            content.append(f"\n{'─' * 70}")
            content.append(f"Tag: {tag_name}")
            content.append(f"File: {manifest_path}")
            content.append(f"{'─' * 70}\n")
            
            try:
                with open(manifest_path, 'r') as f:
                    manifest_data = json.load(f)
                    content.append(json.dumps(manifest_data, indent=2))
            except Exception as e:
                content.append(f"Error reading manifest: {e}")
        
        content.append("\n" + "=" * 70)
        content.append(f"Total manifests: {len(manifests)}")
        content.append("=" * 70)
        
        # Display with pager
        pydoc.pager('\n'.join(content))
        
    except ImportError:
        # Fallback: print to console
        print("\n" + "=" * 70)
        print("MANIFEST REVIEW (pydoc not available)")
        print("=" * 70)
        
        for tag_name, manifest_path in manifests.items():
            print(f"\nTag: {tag_name}")
            print(f"Manifest file: {manifest_path}")
            print("Please review the manifest files in the directory.")
        
        print("\n" + "=" * 70)
        print(f"Total manifests: {len(manifests)}")
        print(f"Review directory: {os.path.dirname(list(manifests.values())[0]) if manifests else 'N/A'}")
        print("=" * 70)
    
    # Ask for confirmation
    while True:
        response = input(f"\nProceed with uploading {len(manifests)} version(s)? [y/N]: ").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no', '']:
            return False
        else:
            print("Please enter 'y' or 'n'")


def upload_manifests(args, manifests: Dict[str, str], repo_root: str):
    """
    Upload all manifests using publish.py script.
    
    Args:
        args: Command line arguments
        manifests: Dictionary mapping tag names to manifest paths
        repo_root: Root directory of the repository
    """
    publish_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'publish.py')
    
    print(f"\nUploading {len(manifests)} version(s)...")
    print("=" * 60)
    
    success_count = 0
    failed_tags = []
    
    for tag_name, manifest_path in manifests.items():
        print(f"\nUploading tag: {tag_name}")
        
        # Build command to call publish.py
        cmd = [
            sys.executable,
            publish_script,
            args.input,
            '--mode', 'upload',
            '--subfolder', args.subfolder,
            '--manifest-path', manifest_path,
            '--project-slug', args.project_slug,
            '--api-url', args.api_url,
            '--api-token', args.api_token
        ]
        
        if args.overwrite:
            cmd.append('--overwrite')
        
        # Execute
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            success_count += 1
        except subprocess.CalledProcessError as e:
            print(f"Error uploading {tag_name}:")
            print(e.stdout)
            print(e.stderr, file=sys.stderr)
            failed_tags.append(tag_name)
    
    print("=" * 60)
    print(f"\nUpload Summary:")
    print(f"  Successful: {success_count}/{len(manifests)}")
    if failed_tags:
        print(f"  Failed tags: {', '.join(failed_tags)}")
    print("\nMass publish complete!")


def main():
    parser = argparse.ArgumentParser(
        description="Mass Publishing Tool for Hub01 - Publish multiple Git tags at once",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  # Publish all tags matching pattern v1.*
  python3 mass_publish.py /path/to/repo --pattern "^v1\\..*" \\
    --project-slug my-project \\
    --api-url https://hub01-shop.srgnis.com/api \\
    --api-token YOUR_TOKEN

  # Publish all tags starting with 'release-'
  python3 mass_publish.py https://github.com/user/repo.git \\
    --pattern "^release-" \\
    --subfolder src/mod \\
    --project-slug my-mod \\
    --api-url https://hub01-shop.srgnis.com/api \\
    --api-token YOUR_TOKEN
        """
    )
    
    # Input args
    parser.add_argument('input', help='Repo path or URL')
    parser.add_argument('--pattern', required=True, help='Regex pattern to match Git tags')
    parser.add_argument('--subfolder', default='.', help='Project subfolder within repo (default: root)')
    
    # Manifest args
    parser.add_argument('--release-type', default='release', 
                        choices=['release', 'beta', 'alpha'],
                        help='Type of the release (default: release)')
    parser.add_argument('--tags', help='Comma-separated tags to add to all versions')
    parser.add_argument('--github-token', default=os.environ.get('GITHUB_TOKEN'), 
                        help='GitHub Token (can also use GITHUB_TOKEN env var)')
    parser.add_argument('--manifest-dir', help='Directory to store manifests (default: temp directory)')
    
    # Upload args
    parser.add_argument('--project-slug', required=True, help='Hub01 Project Slug')
    parser.add_argument('--api-url', required=True, help='Hub01 API URL')
    parser.add_argument('--api-token', default=os.environ.get('HUB01_API_TOKEN'), help='Hub01 API Token (can also use HUB01_API_TOKEN env var)')
    parser.add_argument('--overwrite', action='store_true', 
                        help='Overwrite existing versions')
    
    args = parser.parse_args()
    
    # Setup temp directory for manifests if not specified
    temp_dir = None
    if args.manifest_dir:
        manifest_dir = os.path.abspath(args.manifest_dir)
        os.makedirs(manifest_dir, exist_ok=True)
    else:
        temp_dir = tempfile.mkdtemp(prefix='mass_publish_')
        manifest_dir = temp_dir
    
    try:
        # Step 1: Setup repository
        print("Setting up repository...")
        if args.input.startswith(('http://', 'https://', 'git@', 'ssh://')):
            # Clone to temp
            clone_dir = tempfile.mkdtemp(prefix='mass_publish_repo_')
            print(f"Cloning {args.input}...")
            repo = git.Repo.clone_from(args.input, clone_dir)
            repo_root = clone_dir
        else:
            # Use local path
            repo_root = os.path.abspath(args.input)
            if not os.path.exists(repo_root):
                print(f"Error: Path does not exist: {repo_root}")
                return 1
            
            try:
                repo = git.Repo(repo_root, search_parent_directories=True)
            except git.InvalidGitRepositoryError:
                print(f"Error: Not a git repository: {repo_root}")
                return 1
        
        # Step 2: Find matching tags
        print(f"\nScanning tags with pattern: {args.pattern}")
        matching_tags = get_matching_tags(repo, args.pattern)
        
        # Step 3: User confirmation for tags
        if not confirm_tags(matching_tags):
            print("Aborted by user.")
            return 0
        
        # Step 4: Generate manifests
        manifests = generate_manifests(args, matching_tags, manifest_dir)
        
        if not manifests:
            print("No manifests were generated. Aborting.")
            return 1
        
        # Step 5: Display manifests for review
        if not display_manifests_for_review(manifests):
            print("Aborted by user.")
            return 0
        
        # Step 6: Upload all manifests
        upload_manifests(args, manifests, repo_root)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Cleanup temp directories
        if temp_dir and os.path.exists(temp_dir):
            print(f"\nCleaning up temporary manifest directory: {temp_dir}")
            shutil.rmtree(temp_dir)
        
        # Cleanup cloned repo if applicable
        if args.input.startswith(('http://', 'https://', 'git@', 'ssh://')):
            if 'clone_dir' in locals() and os.path.exists(clone_dir):
                print(f"Cleaning up cloned repository: {clone_dir}")
                shutil.rmtree(clone_dir)


if __name__ == '__main__':
    sys.exit(main())
