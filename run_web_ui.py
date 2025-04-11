#!/usr/bin/env python3
"""
Run the Chef to Ansible Converter Web UI
"""

import os
import sys
import argparse
from web.app import app

def main():
    parser = argparse.ArgumentParser(description='Run the Chef to Ansible Converter Web UI')
    parser.add_argument('--host', default='0.0.0.0', help='Host to run the web UI on (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the web UI on (default: 5000)')
    parser.add_argument('--debug', action='store_true', default=True, help='Run in debug mode (default: True)')
    parser.add_argument('--api-key', help='Anthropic API key (default: ANTHROPIC_API_KEY env var)')
    parser.add_argument('--log-level', default='DEBUG', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Logging level (default: DEBUG)')
    
    args = parser.parse_args()
    
    if args.api_key:
        os.environ['ANTHROPIC_API_KEY'] = args.api_key
    
    # Configure logging
    import logging
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Set Flask app logging
    app.logger.setLevel(log_level)
    
    print(f"Starting Chef to Ansible Converter Web UI on http://{args.host}:{args.port}")
    print(f"API Key: {'Set' if os.environ.get('ANTHROPIC_API_KEY') else 'Not set'}")
    print(f"Debug Mode: {args.debug}")
    print(f"Log Level: {args.log_level}")
    print("Press Ctrl+C to stop the server")
    
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()
