#!/usr/bin/env python3

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.validator import AnsibleValidator

# Initialize validator
validator = AnsibleValidator(verbose=True)

# Test with our sample role
print("=== Testing Valid Role ===")
validator.validate("tests/test_role")

# Test with invalid role
print("\n=== Testing Invalid Role ===")
validator.validate("tests/nonexistent_role")
