#!/usr/bin/env bash
#
# RSCDAgent.sh - Remote Sensing Change Detection Paper Reproduction Agent
# Based on Paper2Agent architecture
#
# Usage:
#   bash RSCDAgent.sh \
#     --project_dir <PROJECT_DIR> \
#     --github_url <GITHUB_URL> \
#     --paper <PAPER_PDF_OR_URL> \
#     --dataset <DATASET_PATH> \
#     --target <TARGET_TABLE_OR_METRICS> \
#     [--benchmark <BENCHMARK>] \
#     [--api <API_KEY>] \
#     [--mode <full|testonly|short>] \
#     [--skip-training]
#

set -e

# ============== Configuration ==============
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}[STEP $1]${NC} $2"; }

# ============== Helper Functions ==============

show_help() {
    cat << EOF
RSCDAgent - Remote Sensing Change Detection Paper Reproduction Agent

Usage:
    bash RSCDAgent.sh [options...]

Options (all optional, collected interactively if missing):
    --project_dir DIR       Project root directory
    --github_url URL        GitHub repository URL
    --local_repo PATH      Local repository path
    --paper PATH            Paper PDF or URL
    --dataset PATH          Dataset path
    --target TEXT          Target metrics table
    --benchmark TEXT       Benchmark dataset (default: LEVIR-CD)
    --mode MODE            Execution mode: full|testonly|short (default: testonly)
                          Supports natural language: "full training", "short", "test only"
    --conda_env NAME       Conda environment name
    --env_path PATH        Conda environment storage path
    --skip-training        Skip training steps
    --mcp-only              Generate MCP Server only
    --linux                Linux server mode
    --api KEY              Private repo API key
    --help                 Show this help message

Examples:
    # Full training mode
    bash RSCDAgent.sh \\
        --project_dir ./my_repro \\
        --github_url https://github.com/author/repo \\
        --paper ./paper.pdf \\
        --dataset ./LEVIR-CD \\
        --target "Table 2" \\
        --mode "full training"

    # Minimal usage (all collected interactively)
    bash RSCDAgent.sh

EOF
}

check_dependencies() {
    log_info "Checking dependencies..."

    PYTHON_CMD="python3"
    command -v python3 &> /dev/null || PYTHON_CMD="python"

    if ! command -v $PYTHON_CMD &> /dev/null; then
        log_error "Python not found"
        exit 1
    fi

    if ! command -v git &> /dev/null; then
        log_error "Git not found"
        exit 1
    fi

    log_success "Dependencies OK"
    echo "$PYTHON_CMD"
}

# ============== Auto-detect Functions ==============

# Auto-detect dataset type from path or structure
auto_detect_dataset_type() {
    local dataset_path="$1"

    # Check for known dataset patterns
    if [[ -f "$dataset_path/README.md" ]] || [[ -d "$dataset_path/LEVIR" ]]; then
        echo "LEVIR-CD"
    elif [[ "$dataset_path" =~ "CDD" ]] || [[ -d "$dataset_path/CDD" ]]; then
        echo "CDD"
    elif [[ "$dataset_path" =~ "SysU" ]] || [[ -d "$dataset_path/SysU-CD" ]]; then
        echo "SysU-CD"
    elif [[ "$dataset_path" =~ "WHU" ]] || [[ -d "$dataset_path/WHU-CD" ]]; then
        echo "WHU-CD"
    else
        # Try to detect from directory structure
        if [[ -d "$dataset_path/train/A" ]] && [[ -d "$dataset_path/train/B" ]]; then
            echo "LEVIR-CD"  # Default to LEVIR-CD structure
        else
            echo "LEVIR-CD"  # Default
        fi
    fi
}

# Auto-detect target metrics from paper/repo
auto_detect_target() {
    local paper_path="$1"
    local repo_path="$2"

    # Try to find metrics in repo README
    if [[ -f "$repo_path/README.md" ]]; then
        # Look for common metric patterns
        if grep -q "F1.*0\." "$repo_path/README.md" 2>/dev/null; then
            echo "Table 2"  # Common location for main results
        fi
    fi

    # Default to Table 2 if no specific match found
    echo "Table 2"
}

# ============== Pre-check and Info Collection ==============

collect_required_info() {
    # Interactively collect required information, check repo and auto-fill missing items
    log_step "PRE" "Pre-check and info collection..."

    local missing_info=()
    local info_collected=()

    echo ""
    echo "--------------------------------------------"
    echo "  Information Check"
    echo "--------------------------------------------"

    # 1. Check project_dir
    if [[ -z "$PROJECT_DIR" ]]; then
        echo ""
        echo "[?] Enter project root directory (for reproduction outputs):"
        read -r PROJECT_DIR
        while [[ -z "$PROJECT_DIR" ]]; do
            echo "[!] Project directory cannot be empty, please re-enter:"
            read -r PROJECT_DIR
        done
        info_collected+=("project_dir=$PROJECT_DIR")
    fi

    # Ensure directory exists
    mkdir -p "$PROJECT_DIR"

    # 2. Check repo source
    if [[ -z "$GITHUB_URL" ]] && [[ -z "$LOCAL_REPO" ]]; then
        echo ""
        echo "[?] Select repository source:"
        echo "    1) GitHub URL"
        echo "    2) Local repository path"
        read -r -p "Select [1/2]: " repo_source

        case "$repo_source" in
            1)
                echo ""
                echo "[?] Enter GitHub repository URL:"
                read -r GITHUB_URL
                while [[ -z "$GITHUB_URL" ]] || [[ ! "$GITHUB_URL" =~ github.com ]]; do
                    echo "[!] Please enter a valid GitHub URL:"
                    read -r GITHUB_URL
                done
                info_collected+=("github_url=$GITHUB_URL")
                ;;
            2)
                echo ""
                echo "[?] Enter local repository path:"
                read -r LOCAL_REPO
                while [[ ! -d "$LOCAL_REPO" ]]; do
                    echo "[!] Directory does not exist, please re-enter:"
                    read -r LOCAL_REPO
                done
                info_collected+=("local_repo=$LOCAL_REPO")
                ;;
            *)
                echo "[!] Invalid selection, will ask for input"
                ;;
        esac
    fi

    # 3. Get repo path and analyze
    if [[ -n "$LOCAL_REPO" ]]; then
        REPO_PATH="$LOCAL_REPO"
    else
        REPO_NAME=$(extract_repo_name "$GITHUB_URL")
        REPO_PATH="$PROJECT_DIR/repo/$REPO_NAME"

        # Clone repo if not already cloned
        if [[ ! -d "$REPO_PATH" ]]; then
            echo ""
            echo "[*] Cloning repository..."
            if [[ -n "$API_KEY" ]]; then
                git clone "https://x-access-token:$API_KEY@github.com/$(echo $GITHUB_URL | sed 's|https://github.com/||')" "$REPO_PATH" 2>/dev/null || true
            else
                git clone "$GITHUB_URL" "$REPO_PATH" 2>/dev/null || true
            fi
        fi
    fi

    # Confirm repo exists
    if [[ ! -d "$REPO_PATH" ]]; then
        echo ""
        echo "[?] Enter local repository path:"
        read -r LOCAL_REPO
        while [[ ! -d "$LOCAL_REPO" ]]; do
            echo "[!] Directory does not exist, please re-enter:"
            read -r LOCAL_REPO
        done
        REPO_PATH="$LOCAL_REPO"
        info_collected+=("local_repo=$LOCAL_REPO")
    fi

    # Analyze repo structure
    if [[ -d "$REPO_PATH" ]]; then
        echo ""
        echo "[*] Analyzing repository structure..."

        # Detect training entry
        TRAIN_ENTRY=$(find "$REPO_PATH" -maxdepth 2 -name "train*.py" 2>/dev/null | head -1)
        TEST_ENTRY=$(find "$REPO_PATH" -maxdepth 2 -name "test*.py" 2>/dev/null | head -1)

        if [[ -n "$TRAIN_ENTRY" ]]; then
            echo "    [+] Found training entry: $(basename $TRAIN_ENTRY)"
        fi
        if [[ -n "$TEST_ENTRY" ]]; then
            echo "    [+] Found test entry: $(basename $TEST_ENTRY)"
        fi

        # Detect config file
        CONFIG_FILE=$(find "$REPO_PATH" -maxdepth 3 -name "*.yaml" -o -name "*.yml" 2>/dev/null | grep -iE "config|setting" | head -1)
        if [[ -n "$CONFIG_FILE" ]]; then
            echo "    [+] Found config file: $(basename $CONFIG_FILE)"
        fi

        # Detect requirements.txt
        if [[ -f "$REPO_PATH/requirements.txt" ]]; then
            echo "    [+] Found requirements.txt"
        fi
    fi

    # 4. Check paper
    if [[ -z "$PAPER" ]]; then
        echo ""
        echo "[?] Enter paper PDF path or arXiv URL:"
        read -r PAPER
        while [[ -z "$PAPER" ]] || ([[ ! -f "$PAPER" ]] && [[ ! "$PAPER" =~ ^http ]]); do
            echo "[!] File does not exist or URL is invalid, please re-enter:"
            read -r PAPER
        done
        info_collected+=("paper=$PAPER")
    fi

    # 5. Check dataset
    if [[ -z "$DATASET" ]]; then
        echo ""
        echo "[?] Enter dataset path:"
        read -r DATASET
        while [[ -z "$DATASET" ]] || [[ ! -d "$DATASET" ]]; do
            echo "[!] Directory does not exist, please re-enter:"
            read -r DATASET
        done
        info_collected+=("dataset=$DATASET")
    fi

    # Auto-detect dataset type
    if [[ -d "$DATASET" ]]; then
        if [[ -d "$DATASET/train" ]] || [[ -d "$DATASET/training" ]]; then
            echo "    [+] Dataset contains training set"
        fi
        if [[ -d "$DATASET/test" ]]; then
            echo "    [+] Dataset contains test set"
        fi
    fi

    # 6. Check target metrics (auto-detect if not provided)
    if [[ -z "$TARGET" ]]; then
        DETECTED_TARGET=$(auto_detect_target "$PAPER" "$REPO_PATH")
        echo ""
        echo "[*] Auto-detected target metrics: $DETECTED_TARGET"
        echo "[?] Enter target metrics table (press Enter to use auto-detected: $DETECTED_TARGET):"
        read -r TARGET
        if [[ -z "$TARGET" ]]; then
            TARGET="$DETECTED_TARGET"
        fi
        info_collected+=("target=$TARGET")
    fi

    # 7. Check execution mode (default: full)
    if [[ -z "$MODE" ]]; then
        echo ""
        echo "[?] Select execution mode (default: full):"
        echo "    1) testonly - Validate with pretrained weights (~20-30 min)"
        echo "    2) short    - Short training (~1-2 hours)"
        echo "    3) full     - Full training (~8-12 hours) [DEFAULT]"
        read -r -p "Select [1/2/3] (press Enter for 3): " mode_choice

        case "$mode_choice" in
            1) MODE="testonly" ;;
            2) MODE="short" ;;
            3|"") MODE="full" ;;
            *) MODE="full" ;;
        esac
        info_collected+=("mode=$MODE")
    fi

    # 8. Check language preference (default: zh)
    if [[ -z "$LANG" ]]; then
        echo ""
        echo "[?] Select output language (default: zh):"
        echo "    1) en  - English"
        echo "    2) zh  - 中文 (Chinese) [DEFAULT]"
        read -r -p "Select [1/2] (press Enter for 2): " lang_choice

        case "$lang_choice" in
            1) LANG="en" ;;
            2|"") LANG="zh" ;;
            *) LANG="zh" ;;
        esac
        info_collected+=("lang=$LANG")
    fi

    # Show collected info summary
    echo ""
    echo "--------------------------------------------"
    echo "  Information Summary"
    echo "--------------------------------------------"
    echo "  Project: $PROJECT_DIR"
    echo "  Repo: $(if [[ -n "$GITHUB_URL" ]]; then echo "$GITHUB_URL"; else echo "$LOCAL_REPO"; fi)"
    echo "  Paper: $PAPER"
    echo "  Dataset: $DATASET"
    echo "  Target: $TARGET"
    echo "  Mode: $MODE"
    echo "  Language: $LANG"
    echo "--------------------------------------------"

    # Confirm to start
    echo ""
    read -r -p "Confirm start reproduction? [Y/n]: " confirm
    case "$confirm" in
        [nN]|[nN][oO])
            echo "Cancelled"
            exit 0
            ;;
        *)
            echo "[*] Starting execution..."
            ;;
    esac

    return 0
}

# ============== Core Steps ==============

extract_repo_name() {
    echo "$1" | sed -E 's/.*[:/]//' | sed 's/\.git$//'
}

# ============== 核心步骤 ==============

step1_parse_paper() {
    log_step "1" "Parsing paper..."
    PYTHON="$1"
    PAPER="$2"
    OUTPUT_DIR="$3"

    if [[ -f "$PAPER" ]] || [[ "$PAPER" == http* ]]; then
        $PYTHON "$SCRIPT_DIR/scripts/parse_paper.py" \
            --paper "$PAPER" \
            --output_dir "$OUTPUT_DIR" \
            --reports_dir "$PROJECT_DIR/reports" \
            > "$OUTPUT_DIR/step1_paper_parse.log" 2>&1 || true

        if [[ -f "$OUTPUT_DIR/step1_paper_parse.json" ]]; then
            log_success "Paper parsing complete"
        else
            log_warn "Paper parsing skipped (requires pdfplumber)"
        fi
    else
        log_warn "Paper file not found, skipping"
    fi
}

step2_inspect_repo() {
    log_step "2" "Inspecting repository..."
    PYTHON="$1"
    REPO_PATH="$2"
    OUTPUT_DIR="$3"

    $PYTHON "$SCRIPT_DIR/scripts/inspect_repo.py" \
        --repo_path "$REPO_PATH" \
        --output_dir "$OUTPUT_DIR" \
        > "$OUTPUT_DIR/step2_repo_parse.log" 2>&1 || true

    if [[ -f "$OUTPUT_DIR/step2_repo_parse.json" ]]; then
        log_success "Repository inspection complete"
    else
        log_warn "Repository inspection skipped"
    fi
}

step3_check_dataset() {
    log_step "3" "Checking dataset..."
    PYTHON="$1"
    DATASET="$2"
    DATASET_TYPE="$3"
    OUTPUT_DIR="$4"

    # Auto-detect dataset type if not provided
    if [[ -z "$DATASET_TYPE" ]] || [[ "$DATASET_TYPE" == "LEVIR-CD" ]]; then
        DATASET_TYPE=$(auto_detect_dataset_type "$DATASET")
        log_info "Auto-detected dataset type: $DATASET_TYPE"
    fi

    $PYTHON "$SCRIPT_DIR/scripts/check_dataset.py" \
        --dataset "$DATASET" \
        --output_dir "$OUTPUT_DIR" \
        --reports_dir "$PROJECT_DIR/reports" \
        --dataset_type "$DATASET_TYPE" \
        --lang "$LANG" \
        > "$OUTPUT_DIR/step3_dataset_check.log" 2>&1 || true

    if [[ -f "$OUTPUT_DIR/step3_dataset_check.json" ]]; then
        log_success "Dataset check complete"
    else
        log_warn "Dataset check skipped"
    fi
}

step4_generate_plan() {
    log_step "4" "Generating execution plan..."
    PYTHON="$1"
    OUTPUT_DIR="$2"
    MODE="$3"

    $PYTHON "$SCRIPT_DIR/scripts/generate_plan.py" \
        --inputs_dir "$OUTPUT_DIR" \
        --output_dir "$OUTPUT_DIR" \
        --lang "$LANG" \
        > "$OUTPUT_DIR/step4_plan.log" 2>&1 || true

    if [[ -f "$OUTPUT_DIR/step4_plan.json" ]]; then
        log_success "Plan generation complete"
    else
        log_warn "Plan generation skipped"
    fi
}

step5_run_repro() {
    log_step "5" "Running reproduction..."

    if [[ "$SKIP_TRAINING" == "true" ]]; then
        log_info "Skipping training (--skip-training)"
        return 0
    fi

    PYTHON="$1"
    PLAN="$2"
    OUTPUT_DIR="$3"
    PROJECT_DIR="$4"

    if [[ "$MODE" == "testonly" ]]; then
        log_info "Mode: Test-only"
    elif [[ "$MODE" == "short" ]]; then
        log_info "Mode: Short training (20 epochs)"
    else
        log_info "Mode: Full training"
    fi

    $PYTHON "$SCRIPT_DIR/scripts/run_repro.py" \
        --plan "$PLAN" \
        --project_dir "$PROJECT_DIR" \
        --output_dir "$OUTPUT_DIR" \
        --lang "$LANG" \
        > "$OUTPUT_DIR/step5_execution.log" 2>&1 || true

    if [[ -f "$OUTPUT_DIR/step5_execution.json" ]]; then
        log_success "Execution complete"
    else
        log_warn "Execution skipped (may require GPU)"
    fi
}

step6_evaluate() {
    log_step "6" "Evaluating results..."
    PYTHON="$1"
    OUTPUT_DIR="$2"
    REPORTS_DIR="$3"

    $PYTHON "$SCRIPT_DIR/scripts/evaluate_repro.py" \
        --inputs_dir "$OUTPUT_DIR" \
        --output_dir "$OUTPUT_DIR" \
        --reports_dir "$REPORTS_DIR" \
        --lang "$LANG" \
        > "$OUTPUT_DIR/step6_evaluation.log" 2>&1 || true

    if [[ -f "$OUTPUT_DIR/step6_evaluation.json" ]]; then
        log_success "Evaluation complete"
    else
        log_warn "Evaluation skipped"
    fi
}

generate_mcp_server() {
    log_step "MCP" "Generating MCP Server..."

    local repo_name="$1"
    local src_dir="$PROJECT_DIR/src"

    if [[ ! -d "$src_dir" ]]; then
        mkdir -p "$src_dir"
    fi

    # Copy template to generate MCP Server
    if [[ -f "$SCRIPT_DIR/src/mcp.py" ]]; then
        cp "$SCRIPT_DIR/src/mcp.py" "$src_dir/${repo_name}_mcp.py"
        log_success "MCP Server generated: $src_dir/${repo_name}_mcp.py"
    else
        log_warn "MCP template not found"
    fi
}

show_summary() {
    local project_dir="$1"
    local repo_name="$2"

    echo ""
    echo "=============================================="
    echo "           RSCDAgent Execution Summary"
    echo "=============================================="
    echo ""
    echo "Project: $project_dir"
    echo "Repo: $repo_name"
    echo "Mode: $MODE"
    echo ""
    echo "Output files:"
    echo "  - claude_outputs/step1_paper_parse.json"
    echo "  - claude_outputs/step2_repo_parse.json"
    echo "  - claude_outputs/step3_dataset_check.json"
    echo "  - claude_outputs/step4_plan.json"
    echo "  - claude_outputs/step5_execution.json"
    echo "  - claude_outputs/step6_evaluation.json"
    echo ""
    echo "Reports:"
    echo "  - reports/paper_summary.md"
    echo "  - reports/dataset_check.md"
    echo "  - reports/reproduction_report.md"
    echo "  - reports/metrics_comparison.xlsx  (NEW)"
    echo ""
    echo "MCP Server:"
    echo "  - src/${repo_name}_mcp.py"
    echo ""
    echo "=============================================="
    echo "  Reproduction Complete!"
    echo "=============================================="
    echo ""
    echo "Next steps:"
    echo "  1. View report: cat reports/reproduction_report.md"
    echo "  2. View Excel comparison: reports/metrics_comparison.xlsx"
    echo "  3. Install MCP: bash scripts/install_mcp.sh"
    echo "  4. Start Claude Code: claude"
    echo ""
}

# ============== 主流程 ==============

main() {
    PROJECT_DIR=""
    GITHUB_URL=""
    LOCAL_REPO=""
    PAPER=""
    DATASET=""
    TARGET=""          # Auto-detect if not provided
    BENCHMARK="LEVIR-CD"
    API_KEY=""
    MODE="full"         # Default to full training
    SKIP_TRAINING="false"
    MCP_ONLY="false"
    CONDA_ENV=""
    ENV_PATH=""
    LINUX_MODE="false"
    LANG="zh"           # Default to Chinese

    # Parse arguments (can be empty, supplemented by interactive collection)
    while [[ $# -gt 0 ]]; do
        case $1 in
            --project_dir) PROJECT_DIR="$2"; shift 2 ;;
            --github_url) GITHUB_URL="$2"; shift 2 ;;
            --local_repo) LOCAL_REPO="$2"; shift 2 ;;
            --paper) PAPER="$2"; shift 2 ;;
            --dataset) DATASET="$2"; shift 2 ;;
            --target) TARGET="$2"; shift 2 ;;
            --benchmark) BENCHMARK="$2"; shift 2 ;;
            --api) API_KEY="$2"; shift 2 ;;
            --mode) MODE="$2"; shift 2 ;;
            --conda_env) CONDA_ENV="$2"; shift 2 ;;
            --env_path) ENV_PATH="$2"; shift 2 ;;
            --skip-training) SKIP_TRAINING="true"; shift ;;
            --mcp-only) MCP_ONLY="true"; shift ;;
            --linux) LINUX_MODE="true"; shift ;;
            --lang) LANG="$2"; shift 2 ;;
            --help|-h) show_help; exit 0 ;;
            *) log_error "Unknown argument: $1"; show_help; exit 1 ;;
        esac
    done

    # Display banner
    echo ""
    echo "=============================================="
    echo "     RSCDAgent - Paper Reproduction Agent"
    echo "     Remote Sensing Change Detection"
    echo "=============================================="
    echo ""

    # Check dependencies
    PYTHON=$(check_dependencies)

    # Pre-check and interactive info collection
    collect_required_info

    # Natural language mode parsing
    if [[ -n "$MODE" ]]; then
        PARSED_MODE=$($PYTHON "$SCRIPT_DIR/scripts/nl_parser.py" --mode_only --input "$MODE" 2>/dev/null || echo "")
        if [[ -n "$PARSED_MODE" ]]; then
            MODE="$PARSED_MODE"
            log_info "Mode parsed: $MODE"
        fi
    fi

    # Initialize project directories
    mkdir -p "$PROJECT_DIR"/{scripts,templates,src,repo,env,claude_outputs,reports,config,schemas,docs}

    # Get repo name and path
    if [[ -n "$LOCAL_REPO" ]]; then
        REPO_PATH="$LOCAL_REPO"
        REPO_NAME=$(basename "$LOCAL_REPO")
    else
        REPO_NAME=$(extract_repo_name "$GITHUB_URL")
        REPO_PATH="$PROJECT_DIR/repo/$REPO_NAME"
    fi

    # Check/create conda environment
    if [[ -n "$CONDA_ENV" ]] || [[ -n "$ENV_PATH" ]]; then
        log_info "Checking conda environment..."
        ENV_NAME="${CONDA_ENV:-rscd_repro_$$}"
        $PYTHON "$SCRIPT_DIR/scripts/env_manager.py" check --repo_path "$REPO_PATH" --requirements "requirements.txt" 2>/dev/null || true

        if [[ -n "$ENV_PATH" ]]; then
            $PYTHON "$SCRIPT_DIR/scripts/env_manager.py" create \
                --name "$ENV_NAME" \
                --requirements "$REPO_PATH/requirements.txt" \
                --env_path "$ENV_PATH" 2>/dev/null || true
        fi
    fi

    # Create config file
    cat > "$PROJECT_DIR/config/project.conf" << EOF
[project]
project_dir=$PROJECT_DIR
repo_name=$REPO_NAME
repo_path=$REPO_PATH
benchmark=$BENCHMARK
mode=$MODE

[inputs]
github_url=$GITHUB_URL
local_repo=$LOCAL_REPO
paper=$PAPER
dataset=$DATASET
target=$TARGET

[environment]
conda_env=$CONDA_ENV
env_path=$ENV_PATH
linux_mode=$LINUX_MODE
EOF

    # If MCP only mode, generate server and return
    if [[ "$MCP_ONLY" == "true" ]]; then
        generate_mcp_server "$REPO_NAME"
        return 0
    fi

    # Execute steps
    OUTPUT_DIR="$PROJECT_DIR/claude_outputs"
    REPORTS_DIR="$PROJECT_DIR/reports"
    PLAN="$OUTPUT_DIR/step4_plan.json"

    step1_parse_paper "$PYTHON" "$PAPER" "$OUTPUT_DIR"
    step2_inspect_repo "$PYTHON" "$REPO_PATH" "$OUTPUT_DIR"
    step3_check_dataset "$PYTHON" "$DATASET" "$BENCHMARK" "$OUTPUT_DIR"
    step4_generate_plan "$PYTHON" "$OUTPUT_DIR" "$MODE"

    # Decide whether to execute based on mode
    if [[ "$SKIP_TRAINING" != "true" ]]; then
        step5_run_repro "$PYTHON" "$PLAN" "$OUTPUT_DIR" "$PROJECT_DIR"
    fi

    step6_evaluate "$PYTHON" "$OUTPUT_DIR" "$REPORTS_DIR"
    generate_mcp_server "$REPO_NAME"

    # Show summary
    show_summary "$PROJECT_DIR" "$REPO_NAME"
}

# Execute main function
main "$@"
