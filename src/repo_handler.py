"""
Repository handler module for the Chef to Ansible converter
"""

import os
import tempfile
import shutil
from pathlib import Path
import git

class GitRepoHandler:
    """Handles Git repository operations"""
    
    def __init__(self):
        """Initialize the repository handler"""
        pass
    
    def clone_repository(self, git_url):
        """
        Clone a Git repository to a temporary directory
        
        Args:
            git_url (str): URL of the Git repository
            
        Returns:
            Path: Path to the cloned repository
        """
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp(prefix="chef_to_ansible_")
        
        try:
            # Clone the repository with depth=1 for a shallow clone
            git.Repo.clone_from(git_url, temp_dir, depth=1)
            return Path(temp_dir)
        except git.GitCommandError as e:
            # Clean up the temporary directory if cloning fails
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to clone repository: {str(e)}")
    
    def cleanup(self, repo_path):
        """
        Clean up temporary files
        
        Args:
            repo_path (Path): Path to the cloned repository
        """
        if repo_path.exists():
            shutil.rmtree(repo_path, ignore_errors=True)
