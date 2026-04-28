#!/usr/bin/env bash
#
# install_mcp.sh - Install RSCDAgent MCP Server to Claude Code
#
# Usage:
#   bash install_mcp.sh [--python PYTHON_PATH] [--mcp MCP_SERVER_PATH]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Default configuration
PYTHON_PATH="${1:-python}"  # or .venv/bin/python
MCP_SERVER_PATH="${2:-$PROJECT_DIR/src/mcp.py}"

# Color output
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
echo "  RSCDAgent MCP Server Installation"
echo "=============================================="
echo ""

# Check arguments
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Usage: bash install_mcp.sh [PYTHON_PATH] [MCP_SERVER_PATH]"
    echo ""
    echo "Arguments:"
    echo "  PYTHON_PATH       Python interpreter path (default: python)"
    echo "  MCP_SERVER_PATH    MCP Server path (default: src/mcp.py)"
    echo ""
    echo "Examples:"
    echo "  bash install_mcp.sh .venv/bin/python src/mcp.py"
    echo "  bash install_mcp.sh"
    exit 0
fi

# Check Python
log_info "Checking Python..."
if ! command -v "$PYTHON_PATH" &> /dev/null; then
    log_error "Python not found: $PYTHON_PATH"
    exit 1
fi

PYTHON_VERSION=$("$PYTHON_PATH" --version 2>&1)
log_success "Python: $PYTHON_VERSION"

# Check MCP Server file
if [[ ! -f "$MCP_SERVER_PATH" ]]; then
    log_error "MCP Server file not found: $MCP_SERVER_PATH"
    exit 1
fi

log_success "MCP Server: $MCP_SERVER_PATH"

# Check MCP SDK
log_info "Checking MCP SDK..."
if ! "$PYTHON_PATH" -c "import mcp" 2>/dev/null; then
    log_warn "MCP SDK not installed, installing..."
    "$PYTHON_PATH" -m pip install mcp -q
    if [ $? -eq 0 ]; then
        log_success "MCP SDK installed"
    else
        log_error "MCP SDK installation failed"
        exit 1
    fi
else
    log_success "MCP SDK already installed"
fi

# Check Claude Code
log_info "Checking Claude Code..."
if ! command -v claude &> /dev/null; then
    log_warn "Claude Code CLI not found or not in PATH"
    log_info "Please ensure Claude Code is installed and MCP support is configured"
    log_info "Install参考: https://docs.anthropic.com/en/docs/claude-code/mcp"
else
    log_success "Claude Code CLI installed"
fi

# Execute installation
echo ""
log_info "Starting MCP Server installation..."
echo ""

if command -v fastmcp &> /dev/null; then
    # Use fastmcp to install
    log_info "Using fastmcp to install..."
    fastmcp install claude-code "$MCP_SERVER_PATH" --python "$PYTHON_PATH"

    if [ $? -eq 0 ]; then
        echo ""
        log_success "=============================================="
        log_success "  MCP Server installed successfully!"
        log_success "=============================================="
        echo ""
        echo "Next steps:"
        echo "  1. Run verify_mcp.sh to verify installation"
        echo "  2. Use in Claude Code:"
        echo ""
        echo "     \$ claude"
        echo '     > Check if this repo can be reproduced'
        echo '     > Analyze reproduction results'
        echo '     > Generate report'
        echo ""
    else
        log_error "Installation failed"
        exit 1
    fi
elif command -v claude &> /dev/null; then
    # Use claude mcp command directly
    log_info "Using claude mcp to install..."

    # Read MCP config
    CLAUDE_CONFIG_DIR="${HOME}/.claude"
    CLAUDE_MCP_CONFIG="${CLAUDE_CONFIG_DIR}/mcp_config.json"

    mkdir -p "$CLAUDE_CONFIG_DIR"

    # Create MCP configuration
    cat > "$CLAUDE_MCP_CONFIG" << EOF
{
  "mcpServers": {
    "rscd-agent": {
      "command": "$PYTHON_PATH",
      "args": ["$MCP_SERVER_PATH"]
    }
  }
}
EOF

    log_success "MCP config written: $CLAUDE_MCP_CONFIG"
    echo ""

    # Verify installation
    log_info "Verifying MCP Server..."
    claude mcp list

    echo ""
    log_success "=============================================="
    log_success "  MCP Server installed successfully!"
    log_success "=============================================="
    echo ""
    echo "MCP Server registered in Claude Code: rscd-agent"
    echo ""
    echo "Usage:"
    echo "  \$ claude"
    echo '  > @rscd-agent Check if this repo can be reproduced'
    echo ""
else
    log_error "Cannot install - Claude Code CLI and fastmcp are not available"
    log_info "Please configure MCP Server manually"
    echo ""
    echo "Manual configuration:"
    echo "  1. Install MCP SDK: pip install mcp"
    echo "  2. Add the following to ~/.claude/mcp_config.json:"
    echo ""
    cat << 'EOF'
{
  "mcpServers": {
    "rscd-agent": {
      "command": "python",
      "args": ["/path/to/src/mcp.py"]
    }
  }
}
EOF
    exit 1
fi
