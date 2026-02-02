# Prompter

Batch prompt runner for Claude CLI. Automates sequential execution of prompts from a file, maintaining conversation context and saving responses to a JSON report.

## Features

- Read prompts from `.txt`, `.md` (separated by `---`) or `.json` files
- Maintain conversation context via session ID
- Graceful interruption handling with continue/exit options
- Flexible configuration via CLI args, config files, or defaults
- JSON report with timestamps and status for each prompt

## Installation

### Using pipx (recommended)

```bash
pipx install git+https://github.com/your-repo/prompter.git
```

### Using Poetry

```bash
git clone https://github.com/your-repo/prompter.git
cd prompter
poetry install
```

### Development

```bash
poetry install
poetry run pytest
```

## Usage

### Basic Usage

```bash
# Run prompts from a markdown file
prompter my_prompts.md

# Run with verbose output
prompter tasks.txt --verbose

# Specify output file
prompter prompts.json --output results.json
```

### Command Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Path for output report JSON file (default: `report.json`) |
| `--verbose` | `-v` | Enable verbose output with progress information |
| `--config` | `-c` | Path to config directory |
| `--app-name` | | Application name for config directory (default: `prompter`) |

### Prompt File Formats

**Text/Markdown (`.txt`, `.md`):**
```
First prompt here
---
Second prompt here
---
Third prompt here
```

**JSON (`.json`):**
```json
[
  "First prompt here",
  "Second prompt here",
  "Third prompt here"
]
```

### Interruption Handling

Press `Ctrl+C` during execution to interrupt. You will be prompted:

```
Interrupted. (N)ext or (E)xit?
```

- `N` - Skip current prompt and continue to next
- `E` - Stop execution and save report

## Configuration

### Priority Order

Settings are resolved with the following priority:

1. **CLI arguments** (highest priority)
2. **Config file** (`setting.json`)
3. **Default values** (lowest priority)

### Config Directory Locations

The application searches for config in this order:

1. Path specified via `--config` argument
2. XDG standard path:
   - Linux/macOS: `~/.config/prompter/`
   - Windows: `%APPDATA%/prompter/`
3. `.config/` folder in project root (detected by `pyproject.toml`)

### setting.json

Application settings file.

```json
{
  "verbose": true,
  "output": "reports/output.json"
}
```

### logger.json

Custom logging configuration using Python's `dictConfig` format.

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "detailed": {
      "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
  },
  "handlers": {
    "console": {
      "class": "logging.StreamHandler",
      "level": "INFO",
      "formatter": "detailed",
      "stream": "ext://sys.stdout"
    },
    "file": {
      "class": "logging.FileHandler",
      "level": "DEBUG",
      "formatter": "detailed",
      "filename": "prompter.log"
    }
  },
  "root": {
    "level": "DEBUG",
    "handlers": ["console", "file"]
  }
}
```

## Output Report

The output JSON report contains an array of entries:

```json
[
  {
    "index": 1,
    "prompt": "Your prompt text",
    "response": {
      "session_id": "abc123",
      "content": "Claude's response..."
    },
    "timestamp": "2024-01-15T10:30:00.123456",
    "status": "success"
  },
  {
    "index": 2,
    "prompt": "Second prompt",
    "response": null,
    "error": "Error message if failed",
    "timestamp": "2024-01-15T10:30:05.654321",
    "status": "error"
  }
]
```

Status values: `success`, `error`, `interrupted`

## Requirements

- Python 3.10+
- Claude CLI installed and configured

## License

MIT
