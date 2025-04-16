#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Chef to Ansible Converter Test Environment Setup ===${NC}"

# Check if Vagrant is installed
if ! command -v vagrant &> /dev/null; then
    echo -e "${RED}Error: Vagrant is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if QEMU plugin is installed
if ! vagrant plugin list | grep -q "vagrant-qemu"; then
    echo -e "${YELLOW}Installing vagrant-qemu plugin...${NC}"
    vagrant plugin install vagrant-qemu
fi

# Clean up any existing VM
echo -e "${YELLOW}Cleaning up any existing VM...${NC}"
vagrant destroy -f || true
rm -rf .vagrant || true

# Create the VM
echo -e "${YELLOW}Creating the VM (this may take a few minutes)...${NC}"
VAGRANT_LOG=info vagrant up

# Check VM status
if vagrant status | grep -q "running"; then
    echo -e "${GREEN}VM is running!${NC}"
else
    echo -e "${RED}VM failed to start properly. Check the logs above for errors.${NC}"
    exit 1
fi

# Wait for SSH to be available (with timeout)
echo -e "${YELLOW}Waiting for SSH to be available...${NC}"
MAX_RETRIES=30
COUNT=0
SSH_AVAILABLE=false

while [ $COUNT -lt $MAX_RETRIES ]; do
    if vagrant ssh -c "echo SSH is working" -- -o ConnectTimeout=5 -p 2345; then
        SSH_AVAILABLE=true
        break
    fi
    echo -e "${YELLOW}Waiting for SSH connection (attempt $COUNT of $MAX_RETRIES)...${NC}"
    COUNT=$((COUNT+1))
    sleep 10
done

if [ "$SSH_AVAILABLE" = true ]; then
    echo -e "${GREEN}SSH connection established!${NC}"
else
    echo -e "${RED}Failed to establish SSH connection after multiple attempts.${NC}"
    echo -e "${YELLOW}Troubleshooting tips:${NC}"
    echo "1. Check if the VM is running with 'vagrant status'"
    echo "2. Verify port forwarding with 'netstat -an | grep 2345'"
    echo "3. Try manually connecting with 'ssh -p 2345 vagrant@127.0.0.1'"
    exit 1
fi

# Run Ansible playbook to test the converted roles
echo -e "${YELLOW}Running Ansible playbook to test converted roles...${NC}"
ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i .vagrant/provisioners/ansible/inventory/vagrant_ansible_inventory test_playbook.yml -v

echo -e "${GREEN}Test completed successfully!${NC}"
