# Prompter

CLI-утилита для автоматизации взаимодействия с Claude Code CLI. Считывает список промптов из файла, последовательно отправляет их в `claude` в режиме headless, поддерживает контекст беседы (session_id) и сохраняет историю ответов в JSON-отчёт.

## Установка

### С помощью pipx (рекомендуется)

```bash
pipx install .
```

### С помощью Poetry

```bash
poetry install
poetry run prompter --help
```

### Для разработки

```bash
poetry install
poetry shell
prompter --help
```

## Использование

### Базовый запуск

```bash
prompter my_prompts.md
```

### С указанием выходного файла

```bash
prompter tasks.txt --output results.json
```

### Verbose режим

```bash
prompter prompts.txt --verbose
```

### Полный пример

```bash
prompter prompts.md \
    --output ./reports/session_report.json \
    --timeout 3600 \
    --verbose \
    --config ~/.config/prompter
```

## Аргументы и флаги

| Аргумент/Флаг | Описание |
|---------------|----------|
| `INPUT_FILE` | Путь к файлу с промптами (.txt, .md или .json) |
| `--output`, `-o` | Путь для сохранения JSON-отчёта (по умолчанию: `report.json`) |
| `--verbose`, `-v` | Включить подробный вывод (DEBUG уровень логирования) |
| `--timeout`, `-t` | Таймаут в секундах для каждого промпта (по умолчанию: 2400) |
| `--config`, `-c` | Путь к директории с конфигурацией |
| `--app-name` | Имя приложения для поиска конфигов (по умолчанию: `prompter`) |

## Форматы входных файлов

### Текстовые файлы (.txt, .md)

Промпты разделяются тремя дефисами (`---`):

```markdown
Напиши функцию для сортировки списка
---
Добавь тесты для этой функции
---
Оптимизируй производительность
```

### JSON файлы (.json)

Массив строк:

```json
[
    "Напиши функцию для сортировки списка",
    "Добавь тесты для этой функции",
    "Оптимизируй производительность"
]
```

## Конфигурация

### Приоритеты настроек

1. **CLI аргументы** (наивысший приоритет)
2. **Файл конфигурации** (`setting.json`)
3. **Значения по умолчанию**

### Поиск директории конфигурации

Программа ищет конфигурацию в следующем порядке:

1. Путь, указанный через `--config`
2. XDG-стандарт:
   - Linux: `~/.config/prompter/`
   - Windows: `%APPDATA%/prompter/`
3. Папка `.config/` в корне проекта (определяется по наличию `pyproject.toml`)

### setting.json

Файл настроек приложения:

```json
{
    "verbose": true,
    "timeout": 3600
}
```

### logger.json

Конфигурация логирования (формат Python `dictConfig`):

```json
{
    "version": 1,
    "disable_existing_loggers": false,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": "prompter.log",
            "encoding": "utf-8"
        }
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console", "file"]
    }
}
```

## Выходной отчёт

Результаты сохраняются в JSON-файл со следующей структурой:

```json
[
    {
        "prompt": "Текст промпта",
        "claude_response": {
            "type": "result",
            "result": "Ответ от Claude..."
        },
        "timestamp": "2024-01-15T10:30:00.123456",
        "status": "success"
    },
    {
        "prompt": "Промпт с ошибкой",
        "claude_response": null,
        "timestamp": "2024-01-15T10:31:00.654321",
        "status": "error",
        "error": "Описание ошибки"
    }
]
```

## Обработка прерываний

При нажатии `Ctrl+C` во время выполнения промпта программа спросит:

```
Interrupted. (R)epeat, (N)ext or (E)xit?
```

- `R` — повторить текущий промпт
- `N` — пропустить текущий промпт и перейти к следующему
- `E` — завершить выполнение и сохранить отчёт

## Требования

- Python 3.10+
- Claude Code CLI (`claude`) должен быть установлен и доступен в PATH

## Лицензия

MIT
