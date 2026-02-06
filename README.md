# Prompter

CLI utility for automating interaction with Claude Code CLI. Prompter reads prompts from a file, sequentially sends them to `claude` in headless mode, maintains conversation context (session_id), and saves response history to a JSON report.

## Installation

### Using pipx (recommended)

```bash
pipx install prompter
```

### Using Poetry

```bash
git clone <repository-url>
cd prompter
poetry install
```

### From source

```bash
pip install .
```

## Usage

### Basic usage

```bash
prompter prompts.txt
```

### With options

```bash
prompter prompts.md --verbose --output results.json
prompter tasks.txt -v -o report.json --timeout 3600
prompter prompts.json --config ~/.config/my-prompter
```

### Command-line options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output` | `-o` | Path to save the output report (JSON) | `report.json` |
| `--verbose` | `-v` | Enable verbose output | `false` |
| `--timeout` | `-t` | Timeout in seconds for each prompt | `2400` |
| `--config` | `-c` | Path to custom config directory | Auto-detected |
| `--app-name` | | Application name for config directory | `prompter` |
| `--version` | | Show version and exit | |
| `--help` | | Show help message | |

### Input file formats

**Text/Markdown (.txt, .md)**

Prompts are separated by `---` on its own line:

```text
First prompt here
---
Second prompt here
---
Third prompt here
```

**JSON (.json)**

Array of strings:

```json
[
  "First prompt here",
  "Second prompt here",
  "Third prompt here"
]
```

### Interrupt handling

During execution, press `Ctrl+C` to interrupt. You will be prompted:

- `R` - Repeat the current prompt
- `N` - Skip to the next prompt
- `E` - Exit and save current results

## Configuration

### Priority order

Settings are resolved in the following order (highest to lowest priority):

1. **CLI arguments** - Command-line flags override everything
2. **Config file** - `setting.json` in config directory
3. **Defaults** - Built-in default values

### Config directory locations

Prompter searches for configuration in the following order:

1. **Explicit path** - If `--config` is provided
2. **XDG standard**:
   - Linux: `~/.config/prompter/`
   - Windows: `%APPDATA%/prompter/`
3. **Project directory** - `.config/` folder in project root (found by `pyproject.toml`)

### Configuration files

#### setting.json

Application settings:

```json
{
  "verbose": true,
  "timeout": 3600
}
```

#### logger.json

Custom logging configuration (Python dictConfig format):

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "standard": {
      "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    },
    "simple": {
      "format": "%(asctime)s - %(message)s"
    }
  },
  "handlers": {
    "console": {
      "class": "logging.StreamHandler",
      "level": "INFO",
      "formatter": "simple",
      "stream": "ext://sys.stdout"
    },
    "file": {
      "class": "logging.FileHandler",
      "level": "DEBUG",
      "formatter": "standard",
      "filename": "prompter.log"
    }
  },
  "root": {
    "level": "DEBUG",
    "handlers": ["console", "file"]
  }
}
```

When using `logger.json`:
- Console handler level is set to `DEBUG` with `--verbose`, otherwise `INFO`
- File handler level is always `DEBUG`
- Root logger level is always `DEBUG`

If no `logger.json` is found, Prompter uses basic logging with:
- Console output: `INFO` level (or `DEBUG` with `--verbose`)
- File output: `DEBUG` level to `prompter.log`

## Output report

Results are saved as a JSON array:

```json
[
  {
    "prompt": "First prompt text",
    "claude_response": {
      "type": "result",
      "result": "Claude's response..."
    },
    "timestamp": "2024-01-15T10:30:00.123456",
    "status": "success"
  },
  {
    "prompt": "Second prompt text",
    "claude_response": null,
    "timestamp": "2024-01-15T10:31:00.654321",
    "status": "error",
    "error": "Error message"
  }
]
```

Status values:
- `success` - Prompt completed successfully
- `error` - Prompt failed with an error
- `skipped` - Prompt was skipped by user (Ctrl+C -> N)

## Requirements

- Python 3.10+
- Claude Code CLI (`claude`) installed and configured

## License

MIT
