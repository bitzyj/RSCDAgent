#!/usr/bin/env bash
#
# verify_mcp.sh - Verify RSCDAgent MCP Server Installation
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "=============================================="
echo "  RSCDAgent MCP Server Verification"
echo "=============================================="
echo ""

# 1. Check Claude Code
log_info "Checking Claude Code CLI..."
if command -v claude &> /dev/null; then
    log_success "Claude Code CLI installed"
else
    log_error "Claude Code CLI not installed"
    exit 1
fi

# 2. Check MCP configuration
log_info "Checking MCP configuration..."
CLAUDE_MCP_CONFIG="${HOME}/.claude/mcp_config.json"
if [[ -f "$CLAUDE_MCP_CONFIG" ]]; then
    log_success "MCP config file exists: $CLAUDE_MCP_CONFIG"
    echo ""
    echo "Currently registered MCP Servers:"
    claude mcp list 2>/dev/null || log_warn "Cannot list MCP Servers"
else
    log_error "MCP configuration not found"
    exit 1
fi

# 3. Check MCP Server response
log_info "Testing MCP Server response..."
echo ""

# Simulate MCP call test
python_cmd="python"
if [[ -f "$PROJECT_DIR/.venv/bin/python" ]]; then
    python_cmd="$PROJECT_DIR/.venv/bin/python"
fi

# Test tool functions
log_info "Testing RSCDTools import..."
if "$python_cmd" -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/src')
from mcp import RSCDTools
print('RSCDTools imported successfully')
" 2>/dev/null; then
    log_success "RSCDTools imported successfully"
else
    log_warn "RSCDTools import failed (MCP SDK may not be installed)"
fi

# 4. Test tools
echo ""
log_info "Testing tool calls..."
echo ""

test_result=$("$python_cmd" -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/src')
from mcp import RSCDTools

# Test check_dataset
result = RSCDTools.check_dataset('/test/dataset', 'LEVIR-CD')
print('check_dataset:', result['status'])

# Test evaluate_repro
result = RSCDTools.evaluate_repro()
print('evaluate_repro:', result['status'])
print('reproduction_status:', result['data']['reproduction_status']['overall'])
" 2>&1)

if [[ $? -eq 0 ]]; then
    echo "$test_result" | while IFS= read -r line; do
        if echo "$line" | grep -q "check_dataset:"; then
            log_success "$line"
        elif echo "$line" | grep -q "evaluate_repro:"; then
            log_success "$line"
        elif echo "$line" | grep -q "reproduction_status:"; then
            log_success "$line"
        fi
    done
else
    log_warn "Some tests failed (this may be normal if MCP SDK is not installed)"
fi

# 5. Summary
echo ""
echo "=============================================="
echo "  Verification Complete"
echo "=============================================="
echo ""
echo "MCP Server Installation Status:"
if command -v claude &> /dev/null && [[ -f "$CLAUDE_MCP_CONFIG" ]]; then
    log_success "Claude Code CLI"
    log_success "MCP config file"
else
    log_error "Installation may be incomplete"
fi
echo ""
echo "Next steps:"
echo "  1. Start Claude Code: claude"
echo "  2. Use @rscd-agent to invoke the Agent"
echo ""
