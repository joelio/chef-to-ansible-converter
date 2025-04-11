"""
Configuration module for the Chef to Ansible converter
"""

class Config:
    """Configuration class for the Chef to Ansible converter"""
    
    def __init__(self, api_key, model='claude-3-7-sonnet-20250219', verbose=False):
        """Initialize the configuration with the given parameters"""
        self.api_key = api_key
        self.model = model
        self.verbose = verbose
        
        # Default conversion settings
        self.max_tokens = 4096
        self.temperature = 0.2
        self.examples_per_request = 3  # Number of examples to include in few-shot learning
        
        # Paths for temporary files
        self.temp_dir = 'temp'
        
        # Timeout settings
        self.api_timeout = 120  # seconds
