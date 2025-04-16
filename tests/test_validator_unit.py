#!/usr/bin/env python3
"""
Unit tests for the Ansible Validator module
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, mock_open

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.validator import AnsibleValidator


class TestAnsibleValidator:
    """Test cases for the AnsibleValidator class"""

    def test_initialization(self):
        """Test validator initialization"""
        validator = AnsibleValidator(verbose=True)
        assert validator.verbose is True
        
        validator = AnsibleValidator(verbose=False)
        assert validator.verbose is False

    def test_validate_success(self):
        """Test successful validation"""
        validator = AnsibleValidator()
        
        # Mock the validation methods
        with patch.object(validator, '_validate_role_structure'):
            with patch.object(validator, '_validate_syntax'):
                with patch.object(validator, '_validate_linting'):
                    with patch.object(validator, '_validate_variable_naming'):
                        with patch.object(validator, '_validate_template_usage'):
                            with patch.object(validator, '_test_role_execution'):
                                with patch.object(validator, '_generate_report'):
                                    result = validator.validate('/path/to/role')
                                    
                                    assert result['valid'] is True
                                    assert 'messages' in result

    def test_validate_failure(self):
        """Test failed validation"""
        validator = AnsibleValidator()
        
        # Add an error to trigger failure
        validator.results['errors'].append('Test error')
        
        # Mock the validation methods to avoid actual validation
        with patch.object(validator, '_validate_role_structure'):
            with patch.object(validator, '_validate_syntax'):
                result = validator.validate('/path/to/role')
                
                assert result['valid'] is False
                assert len(result['messages']) >= 1

    def test_validate_syntax(self):
        """Test YAML syntax validation"""
        validator = AnsibleValidator()
        
        # Create a test file structure
        with patch('os.path.exists', return_value=True):
            with patch('os.path.join', return_value='/path/to/role/tasks/main.yml'):
                with patch('builtins.open', mock_open(read_data='key: value')):
                    with patch('yaml.safe_load'):
                        # Call the method
                        validator._validate_syntax('/path/to/role')
                        
                        # Check that no errors were added
                        assert len(validator.results['errors']) == 0

    @patch('subprocess.run')
    def test_validate_linting(self, mock_run):
        """Test ansible-lint validation"""
        validator = AnsibleValidator()
        
        # Mock successful subprocess run
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_run.return_value = mock_process
        
        # Call the method
        validator._validate_linting('/path/to/role')
        
        # Check that no errors were added
        assert len(validator.results['errors']) == 0
        assert len(validator.results['passed']) >= 1
        
        # Verify subprocess.run was called
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_test_role_execution(self, mock_run):
        """Test role execution validation"""
        validator = AnsibleValidator()
        
        # Mock successful subprocess run
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "PLAY RECAP ************"
        mock_run.return_value = mock_process
        
        # Mock tempfile creation
        with patch('tempfile.NamedTemporaryFile'):
            # Call the method
            validator._test_role_execution('/path/to/role')
            
            # Check that no errors were added
            assert len(validator.results['errors']) == 0
            assert len(validator.results['passed']) >= 1

    def test_generate_report(self):
        """Test generating validation report"""
        validator = AnsibleValidator()
        
        # Add some test results
        validator.results['passed'].append('Test passed')
        validator.results['warnings'].append('Test warning')
        validator.results['errors'].append('Test error')
        
        # Call the method
        validator._generate_report()
        
        # Nothing to assert since this method only logs output
        # We're just making sure it doesn't raise exceptions
