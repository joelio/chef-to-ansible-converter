"""
Tests for the repository handler module.
"""

import os
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.repo_handler import GitRepoHandler


class TestGitRepoHandler(unittest.TestCase):
    """Test cases for the GitRepoHandler class."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_handler = GitRepoHandler()
        self.test_url = "https://github.com/example/repo.git"
        
        # Create a temporary directory for test artifacts
        self.temp_dir = tempfile.mkdtemp(prefix="test_chef_to_ansible_")
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up the temporary directory
        if hasattr(self, 'temp_dir') and self.temp_dir and Path(self.temp_dir).exists():
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('subprocess.run')
    def test_init_git_available(self, mock_run):
        """Test initialization when git is available."""
        # Mock successful git version check
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process
        
        # Initialize the handler
        handler = GitRepoHandler()
        
        # Verify git version was checked
        mock_run.assert_called_once_with(
            ['git', '--version'], 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
    
    @patch('subprocess.run')
    @patch('builtins.print')
    def test_init_git_not_available(self, mock_print, mock_run):
        """Test initialization when git is not available."""
        # Mock git version check failure
        mock_run.side_effect = subprocess.SubprocessError("Git not found")
        
        # Initialize the handler
        handler = GitRepoHandler()
        
        # Verify warning was printed
        mock_print.assert_called_once_with(
            "WARNING: Git executable not found or not working properly. Some features may be limited."
        )
    
    @patch('subprocess.run')
    @patch('tempfile.mkdtemp')
    def test_clone_repository_success(self, mock_mkdtemp, mock_run):
        """Test successful repository cloning."""
        # Mock temporary directory creation
        mock_mkdtemp.return_value = self.temp_dir
        
        # Mock successful git clone
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process
        
        # Clone the repository
        result = self.repo_handler.clone_repository(self.test_url)
        
        # Verify the result
        self.assertEqual(result, Path(self.temp_dir))
        
        # Verify git clone was called correctly
        mock_run.assert_called_once_with(
            ['git', 'clone', '--depth=1', self.test_url, self.temp_dir],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    
    @patch('subprocess.run')
    @patch('tempfile.mkdtemp')
    @patch('shutil.rmtree')
    def test_clone_repository_failure(self, mock_rmtree, mock_mkdtemp, mock_run):
        """Test repository cloning failure."""
        # Mock temporary directory creation
        mock_mkdtemp.return_value = self.temp_dir
        
        # Mock git clone failure
        error = subprocess.SubprocessError("Clone failed")
        error.stderr = "Error: repository not found"
        mock_run.side_effect = error
        
        # Attempt to clone the repository
        with self.assertRaises(RuntimeError) as context:
            self.repo_handler.clone_repository(self.test_url)
        
        # Verify the error message
        self.assertIn("Failed to clone repository", str(context.exception))
        self.assertIn("Error: repository not found", str(context.exception))
        
        # Verify temporary directory was cleaned up
        mock_rmtree.assert_called_once_with(self.temp_dir, ignore_errors=True)
    
    @patch('pathlib.Path.exists')
    @patch('shutil.rmtree')
    def test_cleanup(self, mock_rmtree, mock_exists):
        """Test cleanup of temporary files."""
        # Mock path exists check
        mock_exists.return_value = True
        
        # Clean up the repository
        repo_path = Path(self.temp_dir)
        self.repo_handler.cleanup(repo_path)
        
        # Verify rmtree was called
        mock_rmtree.assert_called_once_with(repo_path, ignore_errors=True)
    
    @patch('pathlib.Path.exists')
    @patch('shutil.rmtree')
    def test_cleanup_nonexistent_path(self, mock_rmtree, mock_exists):
        """Test cleanup with a nonexistent path."""
        # Mock path exists check
        mock_exists.return_value = False
        
        # Clean up with a nonexistent path
        repo_path = Path("/nonexistent/path")
        self.repo_handler.cleanup(repo_path)
        
        # Verify rmtree was not called
        mock_rmtree.assert_not_called()


if __name__ == '__main__':
    unittest.main()
