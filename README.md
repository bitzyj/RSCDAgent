# RSCDAgent：Remote Sensing Change Detection Agent

**Remote Sensing Change Detection Agent** — An automated paper reproduction system for remote sensing image change detection research.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📖 Overview

RSCDAgent automates the reproduction of remote sensing change detection papers. Given a paper, its GitHub repository, and a dataset, it:

1. **Parses** the paper to extract target metrics, training parameters, and experimental setup
2. **Inspects** the repository structure to locate entry points, configs, and training scripts
3. **Validates** the dataset (A/B/label pairing, image dimensions, train/val/test splits)
4. **Plans** an execution strategy based on the target mode (test-only / short / full training)
5. **Executes** the reproduction with command whitelisting and fault-tolerance protections
6. **Evaluates** results and produces a gap analysis report against paper benchmarks

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Git
- Claude Code (for MCP integration)
- (Optional) CUDA-capable GPU for training modes

### Installation

```bash
# Clone the repository
git clone https://github.com/bitzyj/RSCDAgent.git
cd RSCDAgent

# Install Python dependencies
pip install -r requirements.txt

```

### Running a Reproduction

```bash
# Full mode (default) - auto-detect dataset and target metrics
bash RSCDAgent.sh \
  --project_dir ./my_repro \
  --github_url https://github.com/justchenhao/BIT_CD \
  --paper ./BIT_CD.pdf \
  --dataset ./LEVIR-CD

# Test-only mode
bash RSCDAgent.sh \
  --project_dir ./my_repro \
  --github_url https://github.com/justchenhao/BIT_CD \
  --paper ./BIT_CD.pdf \
  --dataset ./LEVIR-CD \
  --mode testonly

# With explicit target and Chinese output (default)
bash RSCDAgent.sh \
  --project_dir ./my_repro \
  --github_url https://github.com/justchenhao/BIT_CD \
  --paper ./BIT_CD.pdf \
  --dataset ./LEVIR-CD \
  --target "Table 2" \
  --mode full \
  --lang zh
```
### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--project_dir` | Yes | - | Project directory to create |
| `--github_url` | Yes | - | GitHub repository URL |
| `--paper` | Yes | - | Path to paper PDF |
| `--dataset` | Yes | - | Path to dataset |
| `--target` | No | Auto-detect | Target metrics table (auto-detect from paper/repo if not specified) |
| `--mode` | No | full | Execution mode: full/testonly/short (default: full) |
| `--lang` | No | zh | Output language: en/zh (default: zh) |

---

## 🤖 Claude Code Integration

After the initial reproduction run, you can create interactive agents by connecting the MCP server to Claude Code.

### Method: Automatic Launch

```bash
# Install MCP server to Claude Code
bash scripts/install_mcp.sh

# Start Claude Code
claude
```

### Using the Agent

Once connected, use natural language to interact:

```
@rscd-agent Check if this repo can be reproduced
@rscd-agent Reproduce this paper
@rscd-agent Analyze reproduction results
@rscd-agent Generate a full reproduction report
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `parse_paper` | Parse paper PDF, extract experimental configuration and target metrics |
| `inspect_repo` | Inspect GitHub repository structure and locate entry points |
| `check_dataset` | Validate remote sensing change detection dataset integrity |
| `generate_plan` | Generate execution plan based on target mode |
| `run_repro` | Execute reproduction task with fault tolerance |
| `evaluate_repro` | Evaluate reproduction results and produce gap analysis |
| `get_status` | Get current reproduction status |
| `stop_repro` | Stop current reproduction task |
| `get_logs` | Retrieve execution logs |
| `get_report` | Get reproduction report in specified format |

---

## 🎬 Usage Modes

| Mode | Description |
|------|-------------|
| `full` | Full training as specified in paper |
| `testonly` | Validate code flow with pretrained weights |
| `short` | Short training run (~20 epochs) |
| `skip` | Parse + check + plan only, no execution |

**Default mode**: `full` (if not specified)

### Interactive Mode

```bash
bash RSCDAgent.sh
```

The script will prompt you for all required information:
- Project directory
- GitHub repository URL
- Paper path
- Dataset path
- Target metrics table
- Execution mode

### Command-line Mode

```bash
# All options specified upfront
bash RSCDAgent.sh \
  --project_dir ./my_repro \
  --github_url https://github.com/author/repo \
  --paper ./paper.pdf \
  --dataset ./LEVIR-CD \
  --target "Table 2" \
  --mode testonly \
  --lang en
```

---

## 📊 Reproduction Case Study

### BIT_CD (IEEE GRSL 2021)

**Paper**: Remote Sensing Image Change Detection with Transformers

| Metric | Paper Target | Achieved | Gap |
|--------|--------------|----------|-----|
| F1 | 0.8988 | 0.8952 | -0.40% |
| IoU | 0.8149 | 0.8076 | -0.90% |
| OA | 0.9841 | 0.9821 | -0.20% |

**Status**: ✅ Fully Reproduced

---

## 📁 Project Structure

```
RSCDAgent/
├── RSCDAgent.sh              # Main entry script
├── scripts/
│   ├── parse_paper.py       # Paper parsing (extract metrics, params)
│   ├── inspect_repo.py      # Repository structure inspection
│   ├── inspect_config.py    # Configuration file parsing
│   ├── check_dataset.py     # Dataset validation (A/B/label pairing)
│   ├── generate_plan.py     # Execution plan generation
│   ├── run_repro.py         # Reproduction executor
│   ├── evaluate_repro.py     # Gap analysis and evaluation
│   ├── generate_patch.py    # Config patch generator
│   ├── metrics.py           # Standardized metrics calculation (cm2score)
│   ├── observability.py     # Structured logging and monitoring
│   ├── circuit_breaker.py   # Retry and rollback mechanisms
│   ├── nl_parser.py         # Natural language mode mapping
│   ├── env_manager.py       # Conda environment management
│   └── export_excel.py      # Excel report export
├── src/
│   └── mcp.py               # MCP Server for Claude Code
├── config/
│   ├── allowed_commands.yaml # Command whitelist (security)
│   ├── file_whitelist.txt   # File modification whitelist
│   └── project.conf         # Project configuration
├── templates/               # Jinja2 report templates
├── claude_outputs/          # Step outputs (JSON)
│   ├── step1_paper_parse.json
│   ├── step2_repo_parse.json
│   ├── step3_dataset_check.json
│   ├── step4_plan_*.json
│   ├── step5_execution.json
│   └── step6_evaluation.json
└── reports/                # Generated reports
    ├── reproduction_report.md
    ├── paper_summary.md
    ├── dataset_check.md
    └── metrics_comparison.xlsx
```

---

## 🏗️ Core Features

### 1. Paper Parsing
Extract model architecture, hyperparameters, dataset information, training configuration, and target metrics from PDF papers.

### 2. Dataset Validation (Domain-Specific)

Remote sensing change detection requires special data integrity checks:

| Check | Description |
|-------|-------------|
| **A/B/label pairing** | Every temporal pair must have corresponding change label |
| **Image dimension uniformity** | All images must have consistent dimensions |
| **Binary label validation** | Change labels must be binary (0/1) |
| **Train/val/test split integrity** | Splits must be properly separated |
| **TIF metadata** | Resolution, projection, and geoinformation verification |

### 3. Standardized Metrics Calculation (cm2score)

| Metric | Formula | Description |
|--------|---------|-------------|
| OA | (TP+TN)/(TP+TN+FP+FN) | Overall Accuracy |
| Rec | TP/(TP+FN) | Recall |
| Pre | TP/(TP+FP) | Precision |
| F1 | 2·Precision·Recall/(Precision+Recall) | F1-Score |
| IoU | TP/(TP+FP+FN) | Jaccard Index |
| Kappa | (p₀-pₑ)/(1-pₑ) | Cohen's Kappa |

### 4. Fault Tolerance

| Feature | Description |
|---------|-------------|
| **Command whitelist** | Only pre-approved commands can execute |
| **Retry with backoff** | Failed commands retry with exponential backoff (3 attempts) |
| **Circuit breaker** | Stops cascading failures after 3 consecutive failures |
| **Rollback support** | Each modification records original state for recovery |
| **Stop request** | User can interrupt between steps via `.stop_requested` marker |

### 5. Observability

- **Structured JSON logging** — Machine-parseable logs in `claude_outputs/logs/`
- **Resource monitoring** — CPU, memory, GPU usage tracked per step
- **Real-time status** — Current status in `execution_status.json`

---

## ⚙️ Configuration

### Command Whitelist (`config/allowed_commands.yaml`)

By default, only safe commands are allowed:

```yaml
allowed_commands:
  - python train.py
  - python test.py
  - python eval.py
  - git clone
  - git checkout

forbidden_patterns:
  - ".*;.*rm.*rf.*"  # Prevents command injection
  - ".*eval.*"       # Prevents eval injection
```

### File Modification Whitelist (`config/file_whitelist.txt`)

Only configuration files in specific directories can be modified:

```
configs/
config/
*.yaml
*.yml
*.json
```

---

## 📤 Output Files

| File | Description |
|------|-------------|
| `step1_paper_parse.json` | Parsed paper information and target metrics |
| `step2_repo_parse.json` | Repository structure and entry points |
| `step3_dataset_check.json` | Dataset validation results |
| `step4_plan_*.json` | Execution plan for selected mode |
| `step5_execution.json` | Execution logs and step results |
| `step6_evaluation.json` | Gap analysis and evaluation results |
| `reproduction_report.md` | Human-readable comprehensive report |
| `paper_summary.md` | Extracted paper information |
| `dataset_check.md` | Dataset validation report |
| `metrics_comparison.xlsx` | Metrics comparison spreadsheet |

---

## 📦 Requirements

```
pip install -r requirements.txt
```

Core dependencies:
- `torch` (CPU or CUDA version)
- `numpy`, `pandas`
- `openpyxl` (Excel export)
- `jinja2` (template rendering)
- `pyyaml` (config parsing)
- `pdfplumber` (paper parsing)
- `psutil` (resource monitoring)
- `mcp` (MCP SDK for Claude Code integration)

---

## 🔗 References

- [Paper2Agent](https://github.com/jmiao24/Paper2Agent) — Reference architecture for paper-to-agent conversion
- [LEVIR-CD](https://justchenhao.github.io/BIT_CD/) — Remote Sensing Image Change Detection Dataset
- [BIT_CD](https://github.com/justchenhao/BIT_CD) — Original implementation

## 📄 License

MIT License