#!/bin/bash
# Script to run the Chef to Ansible Converter Docker container

set -e

# Default values
CHEF_REPO_PATH="./chef-repo"
OUTPUT_PATH="./output"
API_KEY=""
MODEL="claude-3-7-sonnet-20250219"
COMMAND="convert"
LOG_LEVEL="INFO"

# Function to display usage information
show_usage() {
  echo "Chef to Ansible Converter Docker Runner"
  echo ""
  echo "Usage: $0 [OPTIONS] COMMAND"
  echo ""
  echo "Commands:"
  echo "  convert    Convert Chef cookbooks to Ansible roles (default)"
  echo "  validate   Validate generated Ansible roles"
  echo "  web        Start the web UI"
  echo "  build      Build the Docker image"
  echo ""
  echo "Options:"
  echo "  --input=PATH     Path to Chef repository (default: $CHEF_REPO_PATH)"
  echo "  --output=PATH    Path for output Ansible roles (default: $OUTPUT_PATH)"
  echo "  --api-key=KEY    Anthropic API key (can also use ANTHROPIC_API_KEY env var)"
  echo "  --model=MODEL    Anthropic model to use (default: $MODEL)"
  echo "  --log-level=LVL  Log level: DEBUG, INFO, WARNING, ERROR (default: $LOG_LEVEL)"
  echo "  --help           Show this help message"
  echo ""
  echo "Examples:"
  echo "  $0 --input=./my-chef-repo --output=./my-ansible convert"
  echo "  $0 --api-key=sk-xxxx web"
  echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --input=*)
      CHEF_REPO_PATH="${1#*=}"
      shift
      ;;
    --output=*)
      OUTPUT_PATH="${1#*=}"
      shift
      ;;
    --api-key=*)
      API_KEY="${1#*=}"
      shift
      ;;
    --model=*)
      MODEL="${1#*=}"
      shift
      ;;
    --log-level=*)
      LOG_LEVEL="${1#*=}"
      shift
      ;;
    --help)
      show_usage
      exit 0
      ;;
    convert|validate|web|build)
      COMMAND="$1"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      show_usage
      exit 1
      ;;
  esac
done

# Check if API key is provided
if [ -z "$API_KEY" ]; then
  # Try to get from environment variable
  if [ -z "$ANTHROPIC_API_KEY" ]; then
    # Try to load from .env file
    if [ -f ".env" ]; then
      echo "Loading API key from .env file..."
      source .env
      API_KEY="$ANTHROPIC_API_KEY"
    fi
  else
    API_KEY="$ANTHROPIC_API_KEY"
  fi
fi

# Validate API key for non-build commands
if [ "$COMMAND" != "build" ] && [ -z "$API_KEY" ]; then
  echo "Error: Anthropic API key is required"
  echo "Please provide it using --api-key=KEY or set the ANTHROPIC_API_KEY environment variable"
  exit 1
fi

# Create directories if they don't exist
mkdir -p "$CHEF_REPO_PATH" "$OUTPUT_PATH"

# Convert paths to absolute paths
CHEF_REPO_PATH=$(realpath "$CHEF_REPO_PATH")
OUTPUT_PATH=$(realpath "$OUTPUT_PATH")

echo "Chef repository path: $CHEF_REPO_PATH"
echo "Output path: $OUTPUT_PATH"
echo "Using API key: ${API_KEY:0:5}...${API_KEY: -4}"
echo "Using model: $MODEL"
echo "Log level: $LOG_LEVEL"
echo "Command: $COMMAND"

# Execute the appropriate command
case "$COMMAND" in
  build)
    echo "Building Docker image..."
    docker build -t chef-to-ansible-converter:latest .
    echo "Docker image built successfully!"
    ;;
  web)
    echo "Starting web UI on port 5000..."
    docker run -it --rm \
      -p 5000:5000 \
      -v "$OUTPUT_PATH:/output" \
      -e ANTHROPIC_API_KEY="$API_KEY" \
      -e ANTHROPIC_MODEL="$MODEL" \
      -e CHEF_TO_ANSIBLE_LOG_LEVEL="$LOG_LEVEL" \
      chef-to-ansible-converter:latest web
    ;;
  convert|validate)
    echo "Running $COMMAND command..."
    docker run -it --rm \
      -v "$CHEF_REPO_PATH:/input" \
      -v "$OUTPUT_PATH:/output" \
      -e ANTHROPIC_API_KEY="$API_KEY" \
      -e ANTHROPIC_MODEL="$MODEL" \
      -e CHEF_TO_ANSIBLE_LOG_LEVEL="$LOG_LEVEL" \
      chef-to-ansible-converter:latest "$COMMAND"
    ;;
  *)
    echo "Unknown command: $COMMAND"
    show_usage
    exit 1
    ;;
esac

echo "Done!"
