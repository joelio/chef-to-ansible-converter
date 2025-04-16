"""
Configuration module for the Chef to Ansible converter
"""

import os
import logging

class Config:
    """Configuration class for the Chef to Ansible converter"""
    
    def __init__(self, api_key=None, model=None, verbose=False, log_level=None, log_file=None):
        """Initialize the configuration with the given parameters"""
        # API settings
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.model = model or os.environ.get('ANTHROPIC_MODEL', 'claude-3-7-sonnet-20250219')
        
        # Logging settings
        self.verbose = verbose
        self.log_level = self._get_log_level(log_level)
        self.log_file = log_file or os.environ.get('CHEF_TO_ANSIBLE_LOG_FILE')
        
        # Default conversion settings
        self.max_tokens = int(os.environ.get('CHEF_TO_ANSIBLE_MAX_TOKENS', '4096'))
        self.temperature = float(os.environ.get('CHEF_TO_ANSIBLE_TEMPERATURE', '0.2'))
        self.examples_per_request = int(os.environ.get('CHEF_TO_ANSIBLE_EXAMPLES', '3'))
        
        # Paths for temporary files
        self.temp_dir = os.environ.get('CHEF_TO_ANSIBLE_TEMP_DIR', 'temp')
        
        # Timeout settings
        self.api_timeout = int(os.environ.get('CHEF_TO_ANSIBLE_API_TIMEOUT', '120'))  # seconds
    
    def _get_log_level(self, log_level=None):
        """Get the log level from environment variable or parameter"""
        if log_level:
            return log_level
            
        env_level = os.environ.get('CHEF_TO_ANSIBLE_LOG_LEVEL', 'INFO').upper()
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return level_map.get(env_level, logging.INFO)
