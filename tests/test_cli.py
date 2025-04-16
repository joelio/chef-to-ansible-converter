#!/usr/bin/env python3
"""
Unit tests for the CLI module
"""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.cli import main, progress_callback


class TestCLI:
    """Test cases for the CLI module"""

    def test_progress_callback(self, capsys):
        """Test the progress callback function"""
        progress_callback("Test message")
        captured = capsys.readouterr()
        assert captured.out == "\rTest message"

    @patch('src.cli.Config')
    @patch('src.cli.ChefParser')
    @patch('src.cli.LLMConverter')
    @patch('src.cli.AnsibleGenerator')
    @patch('src.cli.AnsibleValidator')
    @patch('sys.argv', ['chef-to-ansible', '/path/to/chef', '--api-key', 'test_key'])
    def test_main_basic_conversion(self, mock_validator, mock_generator, mock_converter, 
                                  mock_parser, mock_config, capsys):
        """Test basic conversion without validation"""
        # Mock the parser to return cookbooks
        mock_parser_instance = mock_parser.return_value
        mock_parser_instance.parse_repository.return_value = [{
            'name': 'test_cookbook',
            'recipes': [],
            'attributes': [],
            'templates': [],
            'files': []
        }]
        
        # Mock the converter to return Ansible code
        mock_converter_instance = mock_converter.return_value
        mock_converter_instance.convert_cookbook.return_value = {
            'tasks': [],
            'handlers': [],
            'variables': {}
        }
        
        # Mock the generator
        mock_generator_instance = mock_generator.return_value
        mock_generator_instance.generate_role.return_value = Path('/path/to/output/test_cookbook')
        
        # Mock Path.mkdir to avoid creating directories
        with patch('pathlib.Path.mkdir'):
            # Run the main function
            with patch('sys.exit') as mock_exit:
                main()
                
                # Verify the function calls
                mock_config.assert_called_once_with(api_key='test_key', verbose=True)
                mock_parser_instance.parse_repository.assert_called_once_with('/path/to/chef')
                mock_converter_instance.convert_cookbook.assert_called_once()
                mock_generator_instance.generate_role.assert_called_once()
                
                # Verify validator was not called
                mock_validator.return_value.validate.assert_not_called()
                
                # Verify exit was not called with error
                mock_exit.assert_not_called()
                
                # Check output messages
                captured = capsys.readouterr()
                assert "Parsing Chef repository" in captured.out
                assert "Processing cookbook: test_cookbook" in captured.out
                assert "Conversion complete!" in captured.out

    @patch('src.cli.Config')
    @patch('src.cli.ChefParser')
    @patch('src.cli.LLMConverter')
    @patch('src.cli.AnsibleGenerator')
    @patch('src.cli.AnsibleValidator')
    @patch('sys.argv', ['chef-to-ansible', '/path/to/chef', '--api-key', 'test_key', '--validate'])
    def test_main_with_validation_success(self, mock_validator, mock_generator, mock_converter, 
                                         mock_parser, mock_config, capsys):
        """Test conversion with successful validation"""
        # Mock the parser to return cookbooks
        mock_parser_instance = mock_parser.return_value
        mock_parser_instance.parse_repository.return_value = [{
            'name': 'test_cookbook',
            'recipes': [],
            'attributes': [],
            'templates': [],
            'files': []
        }]
        
        # Mock the converter to return Ansible code
        mock_converter_instance = mock_converter.return_value
        mock_converter_instance.convert_cookbook.return_value = {
            'tasks': [],
            'handlers': [],
            'variables': {}
        }
        
        # Mock the generator
        mock_generator_instance = mock_generator.return_value
        mock_generator_instance.generate_role.return_value = Path('/path/to/output/test_cookbook')
        
        # Mock the validator with successful validation
        mock_validator_instance = mock_validator.return_value
        mock_validator_instance.validate.return_value = {
            'valid': True,
            'messages': []
        }
        
        # Mock Path.mkdir to avoid creating directories
        with patch('pathlib.Path.mkdir'):
            # Run the main function
            with patch('sys.exit') as mock_exit:
                main()
                
                # Verify validator was called
                mock_validator_instance.validate.assert_called_once_with('/path/to/output/test_cookbook')
                
                # Verify exit was not called with error
                mock_exit.assert_not_called()
                
                # Check output messages
                captured = capsys.readouterr()
                assert "Validating role: test_cookbook" in captured.out
                assert "Conversion complete!" in captured.out

    @patch('src.cli.Config')
    @patch('src.cli.ChefParser')
    @patch('src.cli.LLMConverter')
    @patch('src.cli.AnsibleGenerator')
    @patch('src.cli.AnsibleValidator')
    @patch('sys.argv', ['chef-to-ansible', '/path/to/chef', '--api-key', 'test_key', '--validate'])
    def test_main_with_validation_failure(self, mock_validator, mock_generator, mock_converter, 
                                         mock_parser, mock_config, capsys):
        """Test conversion with failed validation"""
        # Mock the parser to return cookbooks
        mock_parser_instance = mock_parser.return_value
        mock_parser_instance.parse_repository.return_value = [{
            'name': 'test_cookbook',
            'recipes': [],
            'attributes': [],
            'templates': [],
            'files': []
        }]
        
        # Mock the converter to return Ansible code
        mock_converter_instance = mock_converter.return_value
        mock_converter_instance.convert_cookbook.return_value = {
            'tasks': [],
            'handlers': [],
            'variables': {}
        }
        
        # Mock the generator
        mock_generator_instance = mock_generator.return_value
        mock_generator_instance.generate_role.return_value = Path('/path/to/output/test_cookbook')
        
        # Mock the validator with failed validation
        mock_validator_instance = mock_validator.return_value
        mock_validator_instance.validate.return_value = {
            'valid': False,
            'messages': ['Error 1', 'Error 2']
        }
        
        # Mock Path.mkdir to avoid creating directories
        with patch('pathlib.Path.mkdir'):
            # Run the main function
            with patch('sys.exit') as mock_exit:
                main()
                
                # Verify validator was called
                mock_validator_instance.validate.assert_called_once_with('/path/to/output/test_cookbook')
                
                # Verify exit was called with error
                mock_exit.assert_called_once_with(1)
                
                # Check output messages
                captured = capsys.readouterr()
                assert "Validation failed for role: test_cookbook" in captured.out
                assert "  - Error 1" in captured.out
                assert "  - Error 2" in captured.out

    @patch('src.cli.Config')
    @patch('src.cli.ChefParser')
    @patch('src.cli.LLMConverter')
    @patch('src.cli.AnsibleGenerator')
    @patch('src.cli.AnsibleValidator')
    @patch('sys.argv', ['chef-to-ansible', '/path/to/chef', '--api-key', 'test_key', '--output', '/custom/output'])
    def test_main_with_custom_output(self, mock_validator, mock_generator, mock_converter, 
                                    mock_parser, mock_config, capsys):
        """Test conversion with custom output directory"""
        # Mock the parser to return cookbooks
        mock_parser_instance = mock_parser.return_value
        mock_parser_instance.parse_repository.return_value = [{
            'name': 'test_cookbook',
            'recipes': [],
            'attributes': [],
            'templates': [],
            'files': []
        }]
        
        # Mock the converter to return Ansible code
        mock_converter_instance = mock_converter.return_value
        mock_converter_instance.convert_cookbook.return_value = {
            'tasks': [],
            'handlers': [],
            'variables': {}
        }
        
        # Mock Path.mkdir to avoid creating directories
        with patch('pathlib.Path.mkdir'):
            # Run the main function
            with patch('sys.exit') as mock_exit:
                main()
                
                # Verify generator was called with custom output path
                mock_generator_instance = mock_generator.return_value
                mock_generator_instance.generate_role.assert_called_once()
                args, _ = mock_generator_instance.generate_role.call_args
                assert '/custom/output/test_cookbook' in str(args[1])
                
                # Check output messages
                captured = capsys.readouterr()
                assert "Generating Ansible roles in: /custom/output" in captured.out

    @patch('src.cli.Config')
    @patch('src.cli.ChefParser')
    @patch('sys.argv', ['chef-to-ansible', '/path/to/chef', '--api-key', 'test_key'])
    def test_main_no_cookbooks_found(self, mock_parser, mock_config, capsys):
        """Test handling of no cookbooks found"""
        # Mock the parser to return no cookbooks
        mock_parser_instance = mock_parser.return_value
        mock_parser_instance.parse_repository.return_value = []
        
        # Run the main function
        with patch('sys.exit') as mock_exit:
            main()
            
            # Verify exit was called with error
            mock_exit.assert_called_once_with(1)
            
            # Check output messages
            captured = capsys.readouterr()
            assert "No cookbooks found in repository!" in captured.out

    @patch('argparse.ArgumentParser.parse_args')
    def test_main_argument_parsing(self, mock_parse_args):
        """Test argument parsing"""
        # Mock the argument parser
        mock_args = MagicMock()
        mock_args.chef_repo = '/path/to/chef'
        mock_args.api_key = 'test_key'
        mock_args.output = '/custom/output'
        mock_args.validate = True
        mock_parse_args.return_value = mock_args
        
        # Mock the rest of the function to avoid actual execution
        with patch('src.cli.Config'):
            with patch('src.cli.ChefParser'):
                with patch('src.cli.LLMConverter'):
                    with patch('src.cli.AnsibleGenerator'):
                        with patch('src.cli.AnsibleValidator'):
                            with patch('pathlib.Path.mkdir'):
                                with patch('sys.exit'):
                                    # Run the main function
                                    main()
                                    
                                    # Verify argument parsing
                                    mock_parse_args.assert_called_once()
