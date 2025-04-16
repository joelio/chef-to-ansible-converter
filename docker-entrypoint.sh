#!/bin/bash
set -e

# Function to display usage information
show_usage() {
  echo "Chef to Ansible Converter Docker Container"
  echo ""
  echo "Usage:"
  echo "  docker run -v /path/to/chef/repo:/input -v /path/to/output:/output chef-to-ansible [OPTIONS]"
  echo ""
  echo "Options:"
  echo "  convert    Convert Chef cookbooks to Ansible roles"
  echo "  validate   Validate generated Ansible roles"
  echo "  web        Start the web UI"
  echo "  --help     Show this help message"
  echo ""
  echo "Environment Variables:"
  echo "  ANTHROPIC_API_KEY         API key for Anthropic Claude (required)"
  echo "  ANTHROPIC_MODEL           Model to use (default: claude-3-7-sonnet-20250219)"
  echo "  CHEF_TO_ANSIBLE_LOG_LEVEL Logging level (default: INFO)"
  echo ""
  echo "Examples:"
  echo "  docker run -v ./chef-repo:/input -v ./output:/output -e ANTHROPIC_API_KEY=sk-xxx chef-to-ansible convert"
  echo "  docker run -p 5000:5000 -e ANTHROPIC_API_KEY=sk-xxx chef-to-ansible web"
}

# Check if API key is set
if [ -z "$ANTHROPIC_API_KEY" ] && [ "$1" != "--help" ] && [ "$1" != "-h" ]; then
  echo "Error: ANTHROPIC_API_KEY environment variable is required"
  echo "Please set it using -e ANTHROPIC_API_KEY=your_api_key"
  exit 1
fi

# Process commands
case "$1" in
  convert)
    shift
    echo "Converting Chef cookbooks to Ansible roles..."
    python /app/cli.py /input /output --api-key "$ANTHROPIC_API_KEY" "$@"
    ;;
  validate)
    shift
    echo "Validating Ansible roles..."
    python /app/cli.py /input /output --api-key "$ANTHROPIC_API_KEY" --validate "$@"
    ;;
  web)
    shift
    echo "Starting web UI on port 5000..."
    cd /app && python /app/run_web_ui.py "$@"
    ;;
  --help|-h)
    show_usage
    ;;
  *)
    if [ $# -eq 0 ]; then
      show_usage
    else
      echo "Unknown command: $1"
      echo "Run 'docker run chef-to-ansible --help' for usage information"
      exit 1
    fi
    ;;
esac
