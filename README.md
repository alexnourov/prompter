# Prompter

**Prompter** — утилита командной строки для автоматизации взаимодействия с Claude CLI. Позволяет выполнять серию промптов из файла, сохранять результаты в JSON-отчёт и управлять сессиями Claude.

## Возможности

- ✅ Пакетное выполнение промптов из файлов различных форматов (`.txt`, `.md`, `.adoc`, `.json`)
- ✅ Поддержка include-директив для переиспользования промптов
- ✅ Сохранение результатов в структурированный JSON-отчёт
- ✅ Управление сессиями Claude (сохранение контекста между промптами)
- ✅ Гибкая конфигурация через CLI аргументы, `settings.json` и переменные окружения
- ✅ Детальное логирование с возможностью кастомизации
- ✅ Обработка прерываний (Ctrl+C) с возможностью продолжения/пропуска/выхода
- ✅ Graceful shutdown при получении SIGTERM

## Установка

### Установка через pipx (рекомендуется)

```bash
pipx install .
```

### Установка через Poetry (для разработки)

```bash
poetry install
```

**Требования:**
- **Python:** 3.10+
- **Claude CLI:** установлен и настроен (`claude` в PATH)

## Использование

### Базовые примеры

```bash
# Выполнить промпты из файла
prompter prompts.md

# Указать выходной файл для отчёта
prompter prompts.md -o results.json

# Включить подробный вывод
prompter prompts.md --verbose

# Установить таймаут для каждого промпта (в секундах)
prompter tasks.txt --timeout 3600

# Использовать кастомную директорию конфигурации
prompter prompts.md --config ~/.my-prompter-config

# Запуск через python -m
python -m prompter prompts.md
```

### Аргументы командной строки

#### Позиционные аргументы

- `INPUT_FILE` — путь к файлу с промптами (обязательный)

#### Опциональные флаги

| Флаг | Краткая форма | Описание | Значение по умолчанию |
|------|---------------|----------|----------------------|
| `--output` | `-o` | Путь к выходному JSON-отчёту | `report.json` |
| `--verbose` | `-v` | Подробный вывод (уровень DEBUG в консоли) | `False` |
| `--timeout` | `-t` | Таймаут для каждого промпта (секунды) | `2400` (40 минут) |
| `--app-name` | — | Имя приложения для поиска конфигурации | `prompter` |
| `--config` | `-c` | Путь к директории конфигурации | автопоиск |
| `--version` | — | Показать версию и выйти | — |
| `--help` | — | Показать справку и выйти | — |

### Форматы входных файлов

#### `.txt` / `.md` — разделитель `---`

```markdown
Создай файл hello.py с функцией hello(), которая возвращает "Hello, World!"
---
Напиши тесты для hello.py с помощью pytest
---
Запусти тесты и исправь ошибки, если они есть
```

**Особенности:**
- Первый блок до разделителя считается метаданными и пропускается
- Поддержка экранирования: `\---` → `---` (не разделитель)
- Поддержка include-директив: `@include: path/to/file.md`

#### `.adoc` — AsciiDoc с разделителем `'''`

```asciidoc
= Промпты для проекта
:doctype: article

Первый блок — метаданные (пропускается)

'''

Создай файл hello.py с функцией hello(), которая возвращает "Hello, World!"

'''

Напиши тесты для hello.py с помощью pytest
```

**Особенности:**
- Автоматическая очистка AsciiDoc-разметки
- Поддержка `include::path[]` директив (конвертируются в `@include:`)
- Первый блок до разделителя — метаданные (пропускается)

#### `.json` — массив строк

```json
[
  "Создай файл hello.py с функцией hello(), которая возвращает \"Hello, World!\"",
  {"$ref": "common/setup.json"},
  "Напиши тесты для hello.py с помощью pytest"
]
```

**Особенности:**
- Массив строк или объектов с `$ref`
- `{"$ref": "path"}` — включение промптов из другого файла
- Рекурсивное разрешение include с защитой от циклов

### Конфигурация

#### Приоритеты

Настройки применяются в следующем порядке (от высшего к низшему):

1. **CLI аргументы** — флаги командной строки
2. **settings.json** — файл настроек в директории конфигурации
3. **Значения по умолчанию** — встроенные в приложение

#### Поиск директории конфигурации

Prompter ищет директорию конфигурации в следующем порядке (3 уровня):

1. **Уровень 1:** `./prompter/` (текущая директория)
2. **Уровень 2:** `./.config/prompter/` (текущая директория)
3. **Уровень 3:** Platform-specific:
   - **Linux/Unix:** `~/.config/prompter/`
   - **macOS:** `~/Library/Application Support/prompter/`
   - **Windows:** `%APPDATA%\prompter\`

Можно явно указать директорию через флаг `--config`:

```bash
prompter prompts.md --config /path/to/config
```

#### Файл `settings.json`

Создайте файл `settings.json` в директории конфигурации:

```json
{
  "verbose": false,
  "timeout": 3600,
  "output": "results.json",
  "source_encoding": null
}
```

**Параметры:**

- `verbose` (bool) — подробный вывод
- `timeout` (int) — таймаут в секундах
- `output` (string) — путь к выходному файлу
- `source_encoding` (string|null) — кодировка входных файлов (`null` = автоопределение)

Пример находится в `examples/settings.json`.

#### Кастомное логирование

Создайте файл `logging.json` в директории конфигурации для настройки логирования:

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "file": {
      "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    },
    "console": {
      "format": "%(asctime)s - %(message)s"
    }
  },
  "handlers": {
    "file": {
      "class": "logging.FileHandler",
      "filename": "prompter.log",
      "formatter": "file",
      "level": "DEBUG"
    },
    "console": {
      "class": "logging.StreamHandler",
      "formatter": "console",
      "level": "INFO"
    }
  },
  "root": {
    "level": "DEBUG",
    "handlers": ["file", "console"]
  }
}
```

По умолчанию логи сохраняются в:
- **Файл:** `<config_dir>/prompter.log` (всегда DEBUG)
- **Консоль:** INFO (или DEBUG при `--verbose`)

Полный пример находится в `examples/logging.json`.

### Прерывание выполнения

#### Ctrl+C (SIGINT)

При нажатии **Ctrl+C** во время выполнения промпта, Prompter останавливает текущий процесс `claude` и предлагает выбор:

```
^C
Interrupted! (R)epeat / (N)ext / (E)xit?
```

- **R (Repeat)** — повторить текущий промпт
- **N (Next)** — пропустить текущий промпт (сохранить как `status: "skipped"`)
- **E (Exit)** — завершить выполнение, сохранить частичный отчёт

При повторном нажатии Ctrl+C во время выбора R/N/E — немедленный выход (код 130).

#### SIGTERM

При получении сигнала **SIGTERM** (например, от `systemd` или `docker stop`):

1. Текущий промпт прерывается
2. Создаётся запись с `status: "error"` и сообщением `"SIGTERM received"`
3. Сохраняется частичный отчёт со всеми выполненными промптами
4. Процесс завершается с кодом **143**

## Структура отчёта

Prompter сохраняет результаты в JSON-файл следующего формата:

```json
[
  {
    "prompt": "Создай файл hello.py...",
    "claude_response": {
      "type": "text",
      "content": "Конечно! Создам файл hello.py..."
    },
    "timestamp": "2026-02-11T12:34:56.789012",
    "status": "success"
  },
  {
    "prompt": "Напиши тесты...",
    "claude_response": null,
    "timestamp": "2026-02-11T12:35:12.345678",
    "status": "timeout",
    "error": "Prompt execution exceeded timeout of 2400 seconds"
  },
  {
    "prompt": "Запусти тесты...",
    "claude_response": null,
    "timestamp": "2026-02-11T12:35:15.123456",
    "status": "skipped"
  }
]
```

**Поля записи:**

- `prompt` (string) — текст промпта
- `claude_response` (object|null) — ответ Claude CLI (NDJSON)
- `timestamp` (string) — время выполнения (ISO 8601)
- `status` (string) — статус: `"success"`, `"error"`, `"timeout"`, `"skipped"`
- `error` (string|null) — сообщение об ошибке (только при `status != "success"`)

**Особенности:**
- Запись отчёта атомарная (temp file + `os.replace`)
- При SIGTERM сохраняется частичный отчёт

## Примеры использования

### Базовый сценарий

```bash
# 1. Создать файл с промптами
cat > tasks.md <<EOF
Создай Python-скрипт для парсинга CSV-файлов
---
Добавь обработку ошибок и валидацию входных данных
---
Напиши unit-тесты с использованием pytest
EOF

# 2. Выполнить промпты
prompter tasks.md -o results.json --verbose

# 3. Проверить результаты
cat results.json | jq '.[] | {status, prompt: .prompt[:50]}'
```

### Использование конфигурации

```bash
# 1. Создать директорию конфигурации
mkdir -p ~/.config/prompter

# 2. Создать settings.json
cat > ~/.config/prompter/settings.json <<EOF
{
  "verbose": true,
  "timeout": 3600,
  "output": "~/prompter-results/report.json"
}
EOF

# 3. Запустить без явных флагов (настройки берутся из settings.json)
prompter prompts.md
```

### Работа с .adoc файлами

```bash
# Создать .adoc файл с промптами
cat > project.adoc <<EOF
= Промпты для проекта
:doctype: article

Метаданные (этот блок будет пропущен)

'''

Создай структуру FastAPI-приложения с базовыми эндпоинтами

'''

Добавь интеграцию с PostgreSQL через SQLAlchemy

'''

Напиши Dockerfile и docker-compose.yml для деплоя
EOF

# Выполнить
prompter project.adoc -o api-project.json
```

## Разработка

### Запуск тестов

```bash
# Все тесты кроме E2E
poetry run python -m pytest tests/ -m "not e2e"

# Только E2E тесты (требуют реального Claude CLI)
poetry run python -m pytest tests/test_e2e.py -v -m e2e

# С coverage
poetry run python -m pytest tests/ -m "not e2e" --cov=src/prompter --cov-report=html
```

См. подробности в `tests/README.md`.

### Структура проекта

```
prompter/
├── src/prompter/          # Исходный код
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py             # CLI и оркестрация
│   ├── config.py          # Управление конфигурацией
│   ├── log.py             # Настройка логирования
│   ├── models.py          # Модели данных
│   ├── report.py          # Генерация отчётов
│   ├── runner.py          # Запуск Claude CLI
│   └── preparer/          # Подсистема подготовки промптов
│       ├── __init__.py
│       ├── text.py        # .txt/.md парсер
│       ├── adoc.py        # .adoc парсер
│       └── json_fmt.py    # .json парсер
├── tests/                 # Тесты (143 теста)
├── specs/                 # Спецификации (SRS, SDD, TS)
├── examples/              # Примеры конфигурации
└── pyproject.toml         # Poetry config
```

## Ссылки

- **Документация:**
  - `specs/SRS.adoc` — Software Requirements Specification
  - `specs/SDD.adoc` — Software Design Document
  - `specs/TS.adoc` — Test Specification
  - `specs/PROMPTS.adoc` — Промпты для разработки

- **Стандарты:**
  - ISO/IEC/IEEE 29148:2018 (SRS)
  - IEEE 1016-2009 (SDD)
  - ISO/IEC/IEEE 29119-3:2021 (TS)

## Лицензия

Этот проект создан в образовательных целях.
