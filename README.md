# Prompter

CLI utility for batch prompt execution with AI coding assistants.

Prompter reads a file of prompts, sends them sequentially to an AI assistant (Claude Code, Gemini CLI, or Aider), and saves a JSON report with results.

## Installation

```bash
# From source (development)
poetry install

# System-wide via pipx
pipx install .
```

## Usage

```bash
# Basic usage (Claude by default)
prompter prompts.md

# Verbose output with custom report path
prompter tasks.txt --verbose -o results.json

# Use Gemini assistant
prompter prompts.md --assistant gemini

# Use Aider assistant
prompter prompts.md --assistant aider

# Dry-run: list prompts without executing
prompter prompts.md --dry-run

# Show version
prompter --version
```

### Arguments and flags

| Argument / Flag       | Description                                          | Default         |
|-----------------------|------------------------------------------------------|-----------------|
| `INPUT_FILE`          | Path to prompts file (`.txt`, `.md`, `.adoc`, `.json`) | *(required)*  |
| `-o`, `--output`      | Output report path                                   | `report.json`   |
| `-v`, `--verbose`     | Enable DEBUG-level console logging                   | `false`         |
| `--app-name`          | Application name for config directory lookup         | `prompter`      |
| `-c`, `--config`      | Explicit path to configuration directory             | *(auto-detect)* |
| `-t`, `--timeout`     | Timeout per prompt in seconds (min 10)               | `2400`          |
| `--source-encoding`   | Force input file encoding (e.g. `utf-8`, `cp1251`)  | *(auto-detect)* |
| `--assistant`         | Assistant to use: `claude`, `gemini`, `aider`        | `claude`        |
| `--dry-run`           | List prompts and exit without execution              | `false`         |
| `--version`           | Show version and exit                                |                 |
| `--help`              | Show help and exit                                   |                 |

## Input file formats

### `.txt` / `.md` (separator `---`)

```markdown
Create a hello.py file with a hello() function that returns "Hello, World!"
---
Write tests for hello.py using pytest
```

Everything before the first separator is treated as metadata and skipped.

### `.adoc` (separator `'''`)

```asciidoc
= Document Title

Create the project structure

'''

Implement the main module
```

AsciiDoc markup (anchors, admonitions, comments) is cleaned from prompt bodies.

### `.json` (array of objects)

```json
[
  {
    "title": "Create project",
    "body": "Create a hello.py file with a hello() function"
  },
  {
    "title": "Write tests",
    "body": "Write tests for hello.py using pytest"
  }
]
```

All formats support include directives for composing prompts from multiple files:
- `.txt`/`.md`: `@include: path/to/file.txt`
- `.adoc`: `include::path/to/file.adoc[]`
- `.json`: `{"$ref": "path/to/file.json"}`

## Configuration

### Priority

Configuration values are resolved in order:

1. **CLI flags** (highest priority)
2. **`settings.json`** in the config directory
3. **Built-in defaults** (lowest priority)

### Config directory search

The config directory is located automatically:

1. **Explicit**: `--config /path/to/dir`
2. **OS-standard**:
   - Linux: `$XDG_CONFIG_HOME/prompter/` (default `~/.config/prompter/`)
   - macOS: `~/Library/Application Support/prompter/`
   - Windows: `%APPDATA%\prompter\`
3. **Project root**: `.config/` directory next to `pyproject.toml`

### `settings.json`

Global parameters and per-assistant sections. See [`examples/settings.json`](examples/settings.json).

### `logging.json`

Custom logging configuration in `logging.config.dictConfig` format. Placed in the config directory. See [`examples/logging.json`](examples/logging.json).

If the file is missing or invalid, a fallback configuration is used: file handler (DEBUG) + console handler (INFO or DEBUG with `--verbose`).

## Assistant configuration

Per-assistant settings are defined as named objects in `settings.json`. The section matching the selected assistant is passed to the runner as-is.

### Claude (default)

No `settings.json` section required. Authentication is managed by Claude Code CLI itself (`claude` must be installed and authenticated).

### Gemini

```json
{
  "gemini": {
    "model": "gemini-2.5-pro"
  }
}
```

Authentication is managed by Gemini CLI (`gemini` must be installed and authenticated).

### Aider

```json
{
  "aider": {
    "api_key": "anthropic=sk-ant-...",
    "anthropic_api_key": null,
    "openai_api_key": null,
    "DEEPSEEK_API_KEY": "sk-...",
    "model": "sonnet"
  }
}
```

**Authentication** (checked in order):
- `api_key` in config (format `PROVIDER=KEY`) -> `--api-key`
- `anthropic_api_key` in config -> `--anthropic-api-key`
- `openai_api_key` in config -> `--openai-api-key`
- Any `*_API_KEY` config key (e.g. `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`) -> `--api-key provider=value`
- Environment variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, etc.

## Interrupt handling

### Ctrl+C (SIGINT)

When you press Ctrl+C during prompt execution, Prompter offers three choices:

```
(R)epeat / (N)ext / (E)xit?
```

- **R** — Repeat the same prompt
- **N** — Skip current prompt (status `skipped`), continue to next
- **E** — Stop execution, save partial report

Pressing Ctrl+C again during the choice prompt terminates immediately (exit code 130).

### SIGTERM

On SIGTERM signal, the current prompt is recorded as `error` with message "Terminated by SIGTERM", a partial report is saved, and the process exits with code 143.

## Report format

The output is a JSON array of prompt results:

```json
[
  {
    "title": "Create project",
    "prompt": "Create a hello.py file...",
    "assistant_response": {"result": "..."},
    "timestamp": "2026-02-17T14:30:00",
    "status": "success"
  }
]
```

Status values: `success`, `skipped`, `error`, `timeout`.
The `error` field is present only for `error` and `timeout` statuses.

## License

MIT
