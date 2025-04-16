"""
Logging configuration for the Chef to Ansible converter
"""
import logging
import sys
from pathlib import Path


def setup_logger(name=None, log_file=None, level=logging.INFO):
    """
    Set up a logger with console and optional file handler
    
    Args:
        name (str, optional): Logger name. If None, returns the root logger
        log_file (str or Path, optional): Path to log file. If None, only logs to console
        level (int, optional): Logging level. Default is INFO
        
    Returns:
        Logger: Configured logger instance
    """
    # Get logger by name or root logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear existing handlers to avoid duplicate messages
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Create console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Create formatters
    console_format = logging.Formatter('%(message)s')
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Add formatter to console handler
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # Add file handler if log_file is specified
    if log_file:
        log_path = Path(log_file) if isinstance(log_file, str) else log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


# Create default logger
logger = setup_logger('chef_to_ansible')
