# MFCQI - Multi-Factor Code Quality Index

[![MFCQI Score](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/bsbodden/mfcqi/main/.github/badges/mfcqi.json)](https://github.com/bsbodden/mfcqi)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/mfcqi.svg)](https://pypi.org/project/mfcqi)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![codecov](https://codecov.io/gh/bsbodden/mfcqi/graph/badge.svg)](https://codecov.io/gh/bsbodden/mfcqi)
![Downloads](https://img.shields.io/pypi/dm/mfcqi)

![logo](https://raw.githubusercontent.com/bsbodden/mfcqi/main/docs/mfcqi.png)

**MFCQI** (Multi-Factor Code Quality Index) is a comprehensive code quality analysis tool that produces a single quality
score (0.0-1.0) by combining multiple evidence-based metrics.

## Why MFCQI?

Traditional code quality tools provide dozens of metrics without a unified quality score. MFCQI provides:

- **Single Score**: One number (0.0-1.0) that represents overall code quality
- **Evidence-Based**: Combines proven metrics using research-backed approach
- **AI-Enhanced**: Optional LLM integration for intelligent recommendations
- **Fast Analysis**: Efficient static analysis of Python codebases
- **No Gaming**: Geometric mean formula prevents gaming individual metrics

## Quick Start

### Installation

```bash
# Install from PyPI with pip
pip install mfcqi

# Or use uv for faster installation
uv pip install mfcqi

# For development (editable install)
git clone https://github.com/bsbodden/mfcqi.git
cd mfcqi
uv pip install -e .
```

### Basic Usage

```bash
# Analyze current directory (metrics only)
mfcqi analyze .

# Analyze specific directory
mfcqi analyze src/mfcqi

# Analyze with AI recommendations (uses your API keys)
mfcqi analyze . --model claude-3-5-sonnet-20241022

# Use local Ollama models
mfcqi analyze . --model ollama:codellama:7b

# Generate more recommendations (default is 10)
mfcqi analyze . --model claude-3-5-sonnet-20241022 --recommendations 15

# Output JSON for CI/CD integration
mfcqi analyze . --format json --output report.json

# Fail CI if quality is below threshold
mfcqi analyze . --min-score 0.75

# Generate a badge for your project
mfcqi badge .  # Shows shields.io URL

# Generate badge JSON for GitHub endpoint
mfcqi badge . -f json -o .github/badges/mfcqi.json
```

### Badge Generation

MFCQI can generate quality badges for your README:

```bash
# Generate a shields.io badge URL
mfcqi badge .

# Generate JSON for dynamic badges
mfcqi badge . -f json -o badge.json

# Get markdown instructions
mfcqi badge . -f markdown
```

The badge automatically uses color coding:

- 🟢 **Green** (≥0.80): Excellent quality
- 🟡 **Yellow** (≥0.60): Good quality
- 🟠 **Orange** (≥0.40): Fair quality
- 🔴 **Red** (<0.40): Poor quality

## The MFCQI Formula

MFCQI uses a Drake Equation-inspired geometric mean to ensure all quality factors matter:

  ```txt
  MFCQI = (M₁ × M₂ × ... × Mₙ)^(1/n)
  ```

Where n is the number of metrics applied (typically 10-13, depending on paradigm).

### Core Metrics (Always Included)

- **Cyclomatic Complexity**: Measures code complexity and modularity
- **Cognitive Complexity**: Measures code understandability and readability
- **Halstead Volume**: Measures program complexity based on operators and operands
- **Maintainability Index**: Combines complexity, volume, and lines of code for readability
- **Code Duplication**: Detects duplicate code blocks across the codebase
- **Documentation Coverage**: Measures docstring coverage for public functions/classes
- **Security (Bandit SAST)**: Analyzes code vulnerability density using CVSS scoring and CWE mapping
- **Dependency Security (pip-audit SCA)**: Scans third-party dependencies for known vulnerabilities
- **Secrets Exposure (detect-secrets)**: Detects hardcoded credentials, API keys, and tokens
- **Code Smell Density**: Multi-layer detection of architectural, design, implementation, and test smells

### Object-Oriented Metrics (Auto-Applied Based on Paradigm)

- **RFC (Response for Class)**: Measures class complexity via method count and calls
- **DIT (Depth of Inheritance Tree)**: Analyzes inheritance structure depth
- **MHF (Method Hiding Factor)**: Evaluates encapsulation quality (private vs public methods)
- **CBO (Coupling Between Objects)**: Measures inter-class coupling for architectural quality
- **LCOM (Lack of Cohesion of Methods)**: Evaluates method cohesion within classes

## Paradigm-Aware Analysis

MFCQI automatically detects your code's programming paradigm (OO or procedural) and applies appropriate metrics:

| Paradigm       | OO Score | Metrics Applied                     | Example                                  |
|----------------|----------|-------------------------------------|------------------------------------------|
| **Strong OO**  | ≥ 0.7    | All metrics including RFC, DIT, MHF | Django models, class-heavy libraries     |
| **Mixed OO**   | 0.4-0.69 | Basic OO metrics (RFC, DIT, MHF)    | Flask apps, mixed-style code             |
| **Weak OO**    | 0.2-0.39 | Limited OO metrics (RFC only)       | Simple class usage                       |
| **Procedural** | < 0.2    | No OO metrics applied               | Data processing scripts, functional code |

This ensures procedural code isn't penalized for lack of OO features, while OO code gets comprehensive assessment.

## LLM Integration

MFCQI seamlessly integrates with LLM providers (via LiteLLM) for intelligent recommendations:

### Configuration

#### Option 1: Using Environment Variables (.env file)

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API keys
# Add your API keys to .env:
# OPENAI_API_KEY=your-key-here
# ANTHROPIC_API_KEY=your-key-here

# Get your API keys from:
# - OpenAI: https://platform.openai.com/api-keys
# - Anthropic: https://console.anthropic.com/settings/keys
```

#### Option 2: Using Secure Keyring (Recommended)

```bash
# Set up API keys using secure system keyring
mfcqi config setup

# Check provider status
mfcqi config status
```

#### Managing Models

```bash
# List available Ollama models
mfcqi models list

# Pull new Ollama model
mfcqi models pull llama3.2
```

## Features

### Formatted Terminal Output

- Rich formatting with colors and tables
- Progress bars and animations
- Clear metrics breakdown
- Prioritized recommendations

### Multiple Output Formats

- **Terminal**: Beautiful formatted output
- **JSON**: For programmatic access
- **HTML**: For reports and dashboards
- **Markdown**: For documentation

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Check Code Quality
  run: |
    pip install mfcqi
    mfcqi analyze src --min-score 0.7 --format json --output mfcqi-report.json

```

### Graceful Degradation

- Works without API keys (metrics-only mode)
- Falls back to local models if available
- Clear messaging about available features

## Metrics Analyzed

### Core Metrics

- **Cyclomatic Complexity**: Measures the number of linearly independent paths through code
- **Cognitive Complexity**: Evaluates how difficult code is to understand
- **Halstead Volume**: Calculates program complexity based on unique operators and operands
- **Maintainability Index**: Composite metric combining complexity, volume, and lines of code
- **Code Duplication**: Percentage of duplicate code blocks in the codebase
- **Documentation Coverage**: Ratio of documented to undocumented public functions/classes
- **Security (Bandit SAST)**: Vulnerability density measured using CVSS scores with CWE categorization
- **Dependency Security (pip-audit SCA)**: Scans dependencies for known CVEs with severity-weighted scoring
- **Secrets Exposure (detect-secrets)**: Detects hardcoded credentials using high-entropy string analysis
- **Code Smell Density**: Aggregated detection of code smells using PyExamine and AST test smell analysis

### Object-Oriented Metrics (Paradigm-Based)

Applied automatically when OO code is detected:

- **RFC (Response for Class)**: Number of methods that can be executed in response to a message
- **DIT (Depth of Inheritance Tree)**: Maximum inheritance path from class to root hierarchy
- **MHF (Method Hiding Factor)**: Ratio of private/protected methods to total methods
- **CBO (Coupling Between Objects)**: Number of classes to which a class is coupled
- **LCOM (Lack of Cohesion of Methods)**: Connected components in method-attribute graph

### Security Metric Details

The Security metric evaluates code vulnerability density using industry-standard approaches:

- **CVSS Scoring**: Each vulnerability is scored using CVSS v3.1 (0-10 scale) based on severity and confidence
- **CWE Mapping**: All Bandit security checks are mapped to specific CWE (Common Weakness Enumeration) IDs
- **Critical Checks**: Certain security checks (e.g., SQL injection, command injection, hardcoded passwords) are never skipped
- **Vulnerability Density**: Calculated as CVSS points per source line of code (SLOC)
- **Normalization**: Uses exponential decay function for smooth scoring gradient
- **Configurable Thresholds**: Default threshold of 0.03 (3 CVSS points per 100 lines) balances security and practicality

## Development

### Prerequisites

- Python 3.10+
- uv (recommended) or pip

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/bsbodden/mfcqi.git
cd mfcqi

# Set up environment variables (for LLM features)
cp .env.example .env
# Edit .env and add your API keys

# Install with development dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=mfcqi --cov-report=term-missing

# Type checking
uv run mypy --strict src/

# Linting
uv run ruff check src/
```

## Expected Score Ranges

Based on the metrics used, typical MFCQI scores for different code quality levels:

| Quality Level | MFCQI Range | Characteristics                                              |
|---------------|-------------|--------------------------------------------------------------|
| Excellent     | 0.80 - 1.00 | Low complexity, well-documented, tested, minimal duplication |
| Good          | 0.60 - 0.79 | Moderate complexity, decent documentation, some tests        |
| Fair          | 0.40 - 0.59 | Higher complexity, sparse documentation, limited testing     |
| Poor          | 0.00 - 0.39 | Very complex, poorly documented, untested code               |

### MFCQI's Own Score

The MFCQI library achieves a score of **0.854** (85.4%) when analyzed on itself:

- **0.854**: Current score analyzing `src/mfcqi`
- **Self-validation**: Demonstrates the metrics in practice on a real codebase
- **Continuous improvement**: Maintained through systematic refactoring

Key metrics:

- **Excellent documentation coverage** (97%): Comprehensive docstrings
- **Excellent cognitive complexity** (91%): Highly readable and understandable code
- **Excellent code duplication** (97%): Minimal redundancy through DRY principles
- **Excellent security score** (80%): Secure subprocess usage and vulnerability management
- **Excellent encapsulation** (MHF: 93%): Proper information hiding
- **Good complexity metrics**: Balanced cyclomatic complexity and Halstead volume
- **Strong overall code quality** in the "Excellent" range (≥0.80)

Example cli usage:

```bash
➜ mfcqi analyze src/mfcqi --model ollama:codellama:7b
⠦ ✅ Metrics calculated (MFCQI Score: 0.85) in 3.0s 0:00:03
⠧ ✅ AI recommendations generated
╭───────────────────────── ✨ MFCQI Analysis Results ──────────────────────────╮
│                                                                              │
│  ⭐ MFCQI Score: 0.854                                                       │
│                                                                              │
│  📊 Metrics Breakdown:                                                       │
│   Metric                      Score     Rating                               │
│   Cyclomatic Complexity        0.74    ✅ Good                               │
│   Cognitive Complexity         0.91  ⭐ Excellent                            │
│   Halstead Volume              0.69    ✅ Good                               │
│   Maintainability Index        0.63    ✅ Good                               │
│   Code Duplication             0.97  ⭐ Excellent                            │
│   Documentation Coverage       0.97  ⭐ Excellent                            │
│   Security Score               0.80  ⭐ Excellent                            │
│   RFC (Response for Class)     1.00  ⭐ Excellent                            │
│   DIT (Depth of Inheritance)   1.00  ⭐ Excellent                            │
│   MHF (Method Hiding Factor)   0.93  ⭐ Excellent                            │
│                                                                              │
│  🤖 AI Recommendations (ollama:codellama:7b):                                │
│    1. 🟡 Use a secure method for handling user input, such as the            │
│  `subprocess` module's `check_output()` function with the `shell=False`      │
│  argument set to `True`. This will help prevent shell injection attacks.     │
│    2. 🟢 Consider using a different library or tool for running              │
│  subprocesses, such as the `psutil` module, which provides more advanced     │
│  features for managing processes.                                            │
│    3. 🟡 Implement input validation and sanitization for all user inputs to  │
│  prevent malicious data from being passed to the subprocess.                 │
│    4. 🟢 Use a secure method for storing sensitive data, such as encrypted   │
│  storage or secure communication protocols.                                  │
│    5. 🟡 Implement access controls and authentication mechanisms to ensure   │
│  that only authorized users can access the subprocesses.                     │
│                                                                              │
│  ⚡ Local processing: 12.3s                                                   │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Research Foundation

MFCQI is based on extensive research in code quality metrics with **Python-specific calibrations** validated against high-quality reference libraries.

### Validation & Calibration (October 2025)

MFCQI underwent some empirical validation to ensure accuracy for Python codebases:

**Reference Libraries Tested**:
- **requests** (0.874) - Gold standard HTTP library
- **click** (0.779) - Comprehensive CLI framework
- **mfcqi itself** (0.854) - Self-scoring validation

**Key Achievement**: Through evidence-based recalibration of 4 metrics (Halstead Volume, Maintainability Index, RFC, DIT), achieved target scores (0.80-0.95) for gold standard libraries. Initial scores were too low due to Java/C++-calibrated thresholds.

**Research Process**:
1. Created 6 synthetic baseline projects for empirical threshold validation
2. Conducted exhaustive literature review (40+ sources) on Python-specific metric behavior
3. Validated against actual high-quality Python libraries
4. Adjusted normalizations based on empirical evidence

### Foundational Research

#### Complexity Metrics
- **Cyclomatic Complexity**: McCabe (1976) - "A Complexity Measure"
- **Cognitive Complexity**: Campbell (2018) - SonarSource validation
- **Halstead Metrics**: Halstead (1977) - "Elements of Software Science"
- **Maintainability Index**: Coleman et al. (1994) - "Using Metrics to Evaluate Software System Maintainability"

#### Object-Oriented Metrics (Python-Calibrated)
- **RFC, DIT, CBO, LCOM**: Chidamber & Kemerer (1994) - "A Metrics Suite for Object Oriented Design"
  - **Critical**: CK metrics validated on C++/Smalltalk, not Python
  - **Recalibrated** based on Python-specific research (see below)
- **MHF, AHF**: Brito e Abreu & Carapuça (1994)

#### Python-Specific Research
- **Papamichail et al. (2022)**: "An Exploratory Study on the Predominant Programming Paradigms in Python Code" (arXiv:2209.01817)
  - 100,000+ projects analyzed, evidence for multi-paradigm nature
- **Tempero et al. (2015)**: "How Do Python Programs Use Inheritance? A Replication Study"
  - Evidence: inheritance used more in Java than Python
- **Prykhodko et al. (2021)**: "A Statistical Evaluation of The Depth of Inheritance Tree Metric for Open-Source Applications Developed in Java"
  - Evidence: DIT 2-5 recommended (class level), no empirical standard exists
- **Churcher & Shepperd (1995)**: "A Critical Analysis of Current OO Design Metrics"
  - Evidence: DIT "not useful indicator of functional correctness"

#### Security Metrics
- **CVSS (Common Vulnerability Scoring System)**: FIRST.org (2019) - "CVSS v3.1 Specification"
- **CWE (Common Weakness Enumeration)**: MITRE Corporation (2024) - "CWE List Version 4.13"
- **Vulnerability Density**: Alhazmi & Malaiya (2005) - "Quantitative Vulnerability Assessment of Systems Software"

### Methodology

MFCQI combines proven metrics using:
- **Geometric mean** aggregation (non-compensatory)
- **Paradigm-aware** metric selection (OO vs procedural detection)
- **Python-specific** threshold calibration
- **Security-conscious** evaluation with CVSS scoring
- **Evidence-based** normalizations validated against reference libraries

**Full research documentation**: See [`docs/research.md`](docs/research.md) for comprehensive citations and calibration details.

## Dependencies and Libraries

MFCQI leverages several specialized libraries for metric extraction:

### Dependencies

#### Core Metric Libraries

| Library                  | Purpose                                                        | PyPI                                                                   |
|--------------------------|----------------------------------------------------------------|------------------------------------------------------------------------|
| **radon**                | Cyclomatic complexity, maintainability index, Halstead metrics | [radon](https://pypi.org/project/radon/)                               |
| **cognitive-complexity** | Cognitive complexity (readability metric)                      | [cognitive-complexity](https://pypi.org/project/cognitive-complexity/) |
| **pylint**               | Static analysis and code quality (subprocess)                 | [pylint](https://pypi.org/project/pylint/)                             |
| **bandit**               | Security vulnerability scanning (subprocess)                   | [bandit](https://pypi.org/project/bandit/)                             |
| **ruff**                 | Fast Python linter (subprocess)                                | [ruff](https://pypi.org/project/ruff/)                                 |

#### Machine Learning & Analysis

| Library          | Purpose                                                | PyPI                                                       |
|------------------|--------------------------------------------------------|------------------------------------------------------------|
| **scikit-learn** | ML models for design pattern detection                | [scikit-learn](https://pypi.org/project/scikit-learn/)     |
| **scipy**        | Optimization algorithms for pattern matching          | [scipy](https://pypi.org/project/scipy/)                   |
| **networkx**     | Graph analysis for code structure                     | [networkx](https://pypi.org/project/networkx/)             |
| **joblib**       | Model persistence and caching                         | [joblib](https://pypi.org/project/joblib/)                 |

#### LLM & Configuration

| Library      | Purpose                                         | PyPI                                                 |
|--------------|------------------------------------------------|------------------------------------------------------|
| **litellm**  | Unified interface for LLM providers            | [litellm](https://pypi.org/project/litellm/)         |
| **pydantic** | Data validation and settings management        | [pydantic](https://pypi.org/project/pydantic/)       |
| **keyring**  | Secure API key storage                         | [keyring](https://pypi.org/project/keyring/)         |

#### CLI & Utilities

| Library      | Purpose                                         | PyPI                                             |
|--------------|------------------------------------------------|--------------------------------------------------|
| **click**    | Command-line interface framework               | [click](https://pypi.org/project/click/)         |
| **rich**     | Terminal formatting and progress bars          | [rich](https://pypi.org/project/rich/)           |
| **requests** | HTTP client for API interactions               | [requests](https://pypi.org/project/requests/)   |
| **toml**     | Configuration file parsing                     | [toml](https://pypi.org/project/toml/)           |

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Links

- [PyPI Package](https://pypi.org/project/mfcqi/)
- [GitHub Repository](https://github.com/bsbodden/mfcqi)
- [Documentation](https://mfcqi.readthedocs.io/)
- [Issue Tracker](https://github.com/bsbodden/mfcqi/issues)

---

Made with ❤️ by BSB
