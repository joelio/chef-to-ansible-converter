#!/usr/bin/env python3
"""
Unit tests for the Config module
"""
import os
import sys
import pytest
import logging
from unittest.mock import patch

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import Config


class TestConfig:
    """Test cases for the Config class"""

    def test_default_initialization(self):
        """Test default configuration initialization"""
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test_key'}):
            config = Config()
            assert config.api_key == 'test_key'
            assert config.model == 'claude-3-7-sonnet-20250219'
            assert config.verbose is False
            assert config.log_level == logging.INFO

    def test_custom_initialization(self):
        """Test custom configuration initialization"""
        config = Config(
            api_key='custom_key',
            model='claude-3-opus-20240229',
            verbose=True,
            log_level='DEBUG'
        )
        assert config.api_key == 'custom_key'
        assert config.model == 'claude-3-opus-20240229'
        assert config.verbose is True
        assert config.log_level == 'DEBUG'

    def test_environment_variables(self):
        """Test environment variable overrides"""
        with patch.dict(os.environ, {
            'ANTHROPIC_API_KEY': 'env_key',
            'ANTHROPIC_MODEL': 'claude-3-haiku-20240307',
            'CHEF_TO_ANSIBLE_LOG_LEVEL': 'WARNING'
        }):
            config = Config()
            assert config.api_key == 'env_key'
            assert config.model == 'claude-3-haiku-20240307'
            assert config.log_level == logging.WARNING

    def test_api_key_none(self):
        """Test behavior when API key is None"""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            assert config.api_key is None

    def test_custom_log_level(self):
        """Test custom log level"""
        config = Config(api_key='test_key', log_level=logging.DEBUG)
        assert config.log_level == logging.DEBUG
        
        # Test with string log level from environment
        with patch.dict(os.environ, {'CHEF_TO_ANSIBLE_LOG_LEVEL': 'DEBUG'}):
            config = Config(api_key='test_key')
            assert config.log_level == logging.DEBUG
