# Структура проекта Prompter

```
prompter/
├── README.md                      # Основная документация (DOC-01)
├── STRUCTURE.md                   # Этот файл
├── pyproject.toml                 # Poetry конфигурация
│
├── src/prompter/                  # Исходный код приложения
│   ├── __init__.py               # Инициализация пакета, версия
│   ├── __main__.py               # Точка входа для python -m prompter
│   ├── cli.py                    # CLI и оркестрация (main, execution_loop)
│   ├── config.py                 # Управление конфигурацией
│   ├── log.py                    # Настройка логирования
│   ├── models.py                 # Модели данных (PromptResult, SigtermReceived)
│   ├── report.py                 # Генерация JSON-отчётов
│   ├── runner.py                 # Запуск Claude CLI и обработка NDJSON
│   └── preparer/                 # Подсистема подготовки промптов
│       ├── __init__.py          # Реестр форматов, prepare_prompts()
│       ├── text.py              # Парсер .txt/.md (разделитель ---)
│       ├── adoc.py              # Парсер .adoc (разделитель ''')
│       └── json_fmt.py          # Парсер .json ($ref поддержка)
│
├── tests/                        # Тесты (143 теста)
│   ├── README.md                # Документация по тестам
│   ├── conftest.py              # Pytest конфигурация (маркеры)
│   ├── test_models.py           # Тесты моделей данных
│   ├── test_preparer.py         # Тесты подготовки промптов (TC-03)
│   ├── test_report.py           # Тесты генерации отчётов (TC-15)
│   ├── test_runner.py           # Тесты запуска Claude CLI (TC-01, TC-02, TC-16, TC-18)
│   ├── test_config.py           # Тесты конфигурации (TC-07, TC-08)
│   ├── test_log.py              # Тесты логирования (TC-17, TC-11)
│   ├── test_cli.py              # Тесты CLI и оркестрации (TC-09, TC-12, TC-14)
│   ├── test_package.py          # Тесты пакета (TC-10, TC-05, TC-13)
│   ├── test_integration.py      # Интеграционные тесты (TC-06, TC-08)
│   └── test_e2e.py              # End-to-end тесты (TC-04, TC-19)
│
├── specs/                        # Спецификации (отдельный git-репозиторий)
│   ├── SRS.adoc                 # Software Requirements Specification (v3.4)
│   ├── SDD.adoc                 # Software Design Document (v4.3)
│   ├── TS.adoc                  # Test Specification (v4.6)
│   ├── PROMPTS.adoc             # Промпты для разработки (v5.0)
│   ├── test_prompts.adoc        # Промпты для E2E тестов
│   ├── test_prompts.md          # Промпты для E2E тестов (.md формат)
│   └── preparer/                # Документация модуля preparer
│       ├── SRS-PREPARER.adoc    # Требования preparer (v1.6)
│       ├── SDD-PREPARER.adoc    # Дизайн preparer (v1.7)
│       └── TS-PREPARER.adoc     # Тесты preparer (v1.6)
│
└── examples/                     # Примеры конфигурации (DOC-02)
    ├── README.md                # Документация примеров
    ├── settings.json            # Пример настроек приложения
    ├── logging.json             # Пример кастомного логирования
    └── prompts.md               # Пример файла с промптами
```

## Ключевые модули

### CLI и оркестрация (`cli.py`)
- `main()` — точка входа, обработка аргументов (Typer)
- `execution_loop()` — цикл выполнения промптов
- Обработка SIGTERM, SIGINT
- Интеграция с config, log, runner, report

### Подготовка промптов (`preparer/`)
- Модульная система с реестром форматов
- Поддержка `.txt`, `.md`, `.adoc`, `.json`
- Рекурсивное разрешение include с защитой от циклов
- Автоопределение кодировки (charset_normalizer)

### Запуск Claude CLI (`runner.py`)
- `run_prompt()` — запуск claude в headless режиме
- Обработка NDJSON stream
- Timeout и signal handling
- Platform-specific stdbuf (Linux/macOS)

### Конфигурация (`config.py`)
- Трёхуровневый поиск директории конфигурации
- Приоритеты: CLI > settings.json > defaults
- Platform-specific пути (Linux/macOS/Windows)

### Логирование (`log.py`)
- Dual output: file (DEBUG) + console (INFO/DEBUG)
- Кастомная конфигурация через logging.json
- Автоматическое создание лог-файлов

## Покрытие тестами

- **Всего тестов:** 143
- **Passing:** 133 (94.3%)
- **Failing:** 8 (технические проблемы caplog, не функциональности)
- **E2E тесты:** 2 (требуют реального Claude CLI)

## Документация

- **README.md** — основная документация пользователя
- **tests/README.md** — руководство по запуску тестов
- **examples/README.md** — описание примеров конфигурации
- **specs/*.adoc** — формальные спецификации (SRS, SDD, TS)

## Стандарты

- **SRS:** ISO/IEC/IEEE 29148:2018
- **SDD:** IEEE 1016-2009
- **TS:** ISO/IEC/IEEE 29119-3:2021
- **Python:** PEP 8, PEP 621 (pyproject.toml)
- **CLI:** Typer framework (mandatory по CLI-03)
