#!/usr/bin/env bash
#
# demo.sh - RSCDAgent End-to-End Demonstration Script
#
# Simulates a complete conversation flow of using RSCDAgent in Claude Code
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "=============================================="
echo "     RSCDAgent - End-to-End Demo"
echo "     Remote Sensing Change Detection"
echo "=============================================="
echo ""

# Demo scenario description
cat << 'INTRO'
This demo shows the complete workflow of RSCDAgent:

1. User invokes @rscd-agent in Claude Code
2. Agent automatically performs: Paper Parsing -> Repo Inspection -> Dataset Check -> Plan Generation -> Execution -> Evaluation
3. Final output: Reproduction report and MCP Server

Demo repository: change_detection_repo (Remote Sensing Image Change Detection)
INTRO

echo ""
echo "Press Enter to start demo..."
read

# ============== Demo Start ==============

section() {
    echo ""
    echo "--------------------------------------------"
    echo -e "${BOLD}${1}${NC}"
    echo "--------------------------------------------"
    sleep 1
}

# Step 1: Paper Parsing
section "Step 1: Paper Parsing"
echo ""
echo -e "${CYAN}User:${NC} @rscd-agent analyze the target metrics from this paper"
echo ""
echo -e "${GREEN}Agent:${NC} Sure, parsing the paper now..."
echo ""
cat << 'PAPER_RESULT'
  Paper: Remote Sensing Image Change Detection
        with Transformers (IEEE GRSL 2021)

  Authors: Hao Chen, Zhenwei Shi
  Year: 2021

  Target Metrics (Table 2):
    - F1: 0.8988
    - IoU: 0.8149
    - OA: 0.9841
    - Precision: 0.9037
    - Recall: 0.8941

  Dataset: LEVIR-CD
PAPER_RESULT

echo ""
echo -e "${GREEN}Agent:${NC} Paper parsed successfully!"
echo ""

read

# Step 2: Repository Inspection
section "Step 2: Repository Inspection"
echo ""
echo -e "${CYAN}User:${NC} Check the repository structure"
echo ""
echo -e "${GREEN}Agent:${NC} Inspecting repository..."
echo ""
cat << 'REPO_RESULT'
  Repo: author/repo
  URL: https://github.com/author/repo

  Directory structure:
  ├── train.py              # Training entry
  ├── test.py               # Test entry
  ├── inference.py          # Inference entry
  ├── configs/
  │   └── BIT-LEVIR.yaml   # Config file
  ├── utils/
  │   └── metrics.py       # Metrics calculation
  └── checkpoints/
      └── BIT_CDD.pth      # Pretrained weights

  Entry points detected:
    - train.py (requires config)
    - test.py
REPO_RESULT

echo ""
echo -e "${GREEN}Agent:${NC} Repository structure analyzed!"
echo ""

read

# Step 3: Dataset Check
section "Step 3: Dataset Check"
echo ""
echo -e "${CYAN}User:${NC} Validate the dataset"
echo ""
echo -e "${GREEN}Agent:${NC} Checking dataset integrity..."
echo ""
cat << 'DATASET_RESULT'
  Dataset: LEVIR-CD
  Path: ./LEVIR-CD

  Split Analysis:
    train/  A: 445  B: 445  label: 445  OK
    val/    A: 64   B: 64   label: 64   OK
    test/   A: 128  B: 128  label: 128  OK

  Pairing Checks:
    A-B matched: YES
    A-label matched: YES

  Integrity: PASS
DATASET_RESULT

echo ""
echo -e "${GREEN}Agent:${NC} Dataset validated successfully!"
echo ""

read

# Step 4: Plan Generation
section "Step 4: Plan Generation"
echo ""
echo -e "${CYAN}User:${NC} Generate execution plan for test-only mode"
echo ""
echo -e "${GREEN}Agent:${NC} Generating plan..."
echo ""
cat << 'PLAN_RESULT'
  Execution Plan (testonly mode):

  Step 1: Parse paper          -> step1_paper_parse.json
  Step 2: Inspect repo          -> step2_repo_parse.json
  Step 3: Check dataset        -> step3_dataset_check.json
  Step 4: Generate plan        -> step4_plan.json
  Step 5: Run reproduction     -> step5_execution.json
  Step 6: Evaluate results     -> step6_evaluation.json

  Mode: testonly (use pretrained weights)
  Estimated time: 20-30 minutes
PLAN_RESULT

echo ""
echo -e "${GREEN}Agent:${NC} Plan generated successfully!"
echo ""

read

# Step 5: Execution
section "Step 5: Reproduction Execution"
echo ""
echo -e "${CYAN}User:${NC} Start reproduction"
echo ""
echo -e "${GREEN}Agent:${NC} Executing plan... (this may take a while)"
echo ""

for i in {1..5}; do
    echo -e "${CYAN}[Step $i]${NC} Executing..."
    sleep 1
done

echo ""
cat << 'EXEC_RESULT'
  Execution Summary:
    Step 1: Paper parsing     SUCCESS (0.5s)
    Step 2: Repo inspection    SUCCESS (1.2s)
    Step 3: Dataset check       SUCCESS (2.8s)
    Step 4: Plan generation     SUCCESS (0.3s)
    Step 5: Reproduction        SUCCESS (1256s)

  Environment:
    Python: 3.8
    PyTorch: 1.12
    CUDA: 11.6
    GPU: NVIDIA RTX 3090
EXEC_RESULT

echo ""
echo -e "${GREEN}Agent:${NC} Execution completed!"
echo ""

read

# Step 6: Evaluation
section "Step 6: Evaluation"
echo ""
echo -e "${CYAN}User:${NC} Evaluate results"
echo ""
echo -e "${GREEN}Agent:${NC} Analyzing results..."
echo ""
cat << 'EVAL_RESULT'
  ==============================================================
                    Reproduction Evaluation Report
  ==============================================================

  Paper: Remote Sensing Image Change Detection
        with Transformers (IEEE GRSL 2021)

  Repo: https://github.com/author/repo
  Reproduction Status: SUCCESS

  Metrics:
    Metric | Paper Target | Achieved | Gap
    -------|--------------|----------|----
    F1     | 0.8988       | 0.8952   | -0.36%
    IoU    | 0.8149       | 0.8076   | -0.73%
    OA     | 0.9841       | 0.9821   | -0.20%

  Conclusion: Code flow validated, suitable for further experiments
  ==============================================================
EVAL_RESULT

echo ""
echo -e "${GREEN}Agent:${NC} Evaluation complete!"
echo ""

# Final Summary
cat << 'FINAL_REPORT'
  ==============================================================
                    RSCDAgent Demo Complete
  ==============================================================

  Paper: Remote Sensing Image Change Detection
        with Transformers (IEEE GRSL 2021)

  Repo: https://github.com/author/repo
  Status: SUCCESS

  Metrics:
    - F1:    0.8952 (target 0.8988, -0.36%)
    - IoU:   0.8076 (target 0.8149, -0.73%)
    - OA:    0.9821 (target 0.9841, -0.20%)

  Execution time: ~25 minutes (Test-only mode)
  Environment: Python 3.8 + PyTorch 1.12 + CUDA 11.6

  Conclusion: Code flow validated, suitable for further experiments
  ==============================================================
FINAL_REPORT

echo ""
echo "Complete report: reports/reproduction_report.md"
echo ""
echo -e "${BOLD}Demo finished! Thank you for watching.${NC}"
echo ""
