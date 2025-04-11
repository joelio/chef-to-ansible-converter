"""
Repository handler module for the Chef to Ansible converter
"""

import os
import tempfile
import shutil
import subprocess
from pathlib import Path

class GitRepoHandler:
    """Handles Git repository operations"""
    
    def __init__(self):
        """Initialize the repository handler"""
        # Check if git is available
        try:
            subprocess.run(['git', '--version'], 
                          check=True, 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE)
        except (subprocess.SubprocessError, FileNotFoundError):
            print("WARNING: Git executable not found or not working properly. Some features may be limited.")
    
    def clone_repository(self, git_url):
        """
        Clone a Git repository to a temporary directory using subprocess
        
        Args:
            git_url (str): URL of the Git repository
            
        Returns:
            Path: Path to the cloned repository
        """
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp(prefix="chef_to_ansible_")
        
        try:
            # Clone the repository with depth=1 for a shallow clone using subprocess
            result = subprocess.run(
                ['git', 'clone', '--depth=1', git_url, temp_dir],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return Path(temp_dir)
        except subprocess.SubprocessError as e:
            # Clean up the temporary directory if cloning fails
            shutil.rmtree(temp_dir, ignore_errors=True)
            error_msg = e.stderr if hasattr(e, 'stderr') else str(e)
            raise RuntimeError(f"Failed to clone repository: {error_msg}")
    
    def cleanup(self, repo_path):
        """
        Clean up temporary files
        
        Args:
            repo_path (Path): Path to the cloned repository
        """
        if repo_path and Path(repo_path).exists():
            shutil.rmtree(repo_path, ignore_errors=True)
