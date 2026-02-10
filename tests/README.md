# Prompter Tests

Этот каталог содержит тесты для утилиты Prompter.

## Структура тестов

- **test_models.py** — модели данных (PromptResult, SigtermReceived)
- **test_preparer.py** — подсистема подготовки промптов (TC-03)
- **test_report.py** — генерация отчетов (TC-15)
- **test_runner.py** — выполнение Claude CLI (TC-01, TC-02, TC-16, TC-18, TC-09)
- **test_config.py** — конфигурация (TC-07, TC-08)
- **test_log.py** — логирование (TC-17, TC-11)
- **test_cli.py** — CLI и оркестрация (TC-09, TC-12, TC-14, TC-15)
- **test_package.py** — валидация пакета (TC-10, TC-05, TC-13, CLI-05)
- **test_integration.py** — интеграционные тесты (TC-06, TC-08)
- **test_e2e.py** — end-to-end тесты (TC-04, TC-19) **требуют реального Claude CLI**

## Запуск тестов

### Стандартные тесты (без E2E)

```bash
# Все тесты кроме e2e
poetry run python -m pytest tests/ -m "not e2e"

# Быстрый прогон (краткий вывод)
poetry run python -m pytest tests/ -m "not e2e" -q

# С подробным выводом
poetry run python -m pytest tests/ -m "not e2e" -v
```

### End-to-End тесты

**Требования:**
- Установленный и настроенный Claude CLI (`claude` в PATH)
- Доступ к Claude API
- Время выполнения: ~10 минут

```bash
# Только e2e тесты
poetry run python -m pytest tests/test_e2e.py -v -m e2e

# Один конкретный e2e тест
poetry run python -m pytest tests/test_e2e.py::test_full_cycle -v -m e2e

# E2E с подробным выводом
poetry run python -m pytest tests/test_e2e.py -v -s -m e2e
```

### Все тесты (включая E2E)

```bash
# Все тесты без фильтрации
poetry run python -m pytest tests/ -v
```

## Статистика

- **Всего тестов:** 143
- **Юнит- и интеграционных:** 141
- **End-to-End:** 2

## Маркеры

- `@pytest.mark.e2e` — тесты, требующие реального Claude CLI

## Coverage

Тесты покрывают требования из следующих документов:
- `specs/SRS.adoc` — Software Requirements Specification
- `specs/TS.adoc` — Test Specification

Детальная трассируемость доступна в `specs/TS.adoc`, раздел §7 (Test Cases).
