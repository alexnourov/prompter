# Примеры конфигурации Prompter

Эта директория содержит примеры конфигурационных файлов для Prompter.

## Файлы

### `settings.json`

Файл настроек приложения. Разместите его в директории конфигурации (например, `~/.config/prompter/settings.json`).

**Параметры:**

- `verbose` (bool) — включить подробный вывод (DEBUG уровень в консоли)
- `timeout` (int) — таймаут для каждого промпта в секундах
- `output` (string) — путь к выходному JSON-отчёту
- `source_encoding` (string|null) — кодировка входных файлов (`null` для автоопределения)

**Использование:**

```bash
# Копировать в директорию конфигурации
mkdir -p ~/.config/prompter
cp examples/settings.json ~/.config/prompter/

# Отредактировать настройки
nano ~/.config/prompter/settings.json

# Запустить prompter (настройки применятся автоматически)
prompter prompts.md
```

### `logging.json`

Кастомная конфигурация логирования (формат `logging.config.dictConfig`).

**Использование:**

```bash
# Копировать в директорию конфигурации
cp examples/logging.json ~/.config/prompter/

# Prompter автоматически загрузит эту конфигурацию при запуске
prompter prompts.md
```

**Кастомизация:**

- Измените формат логов в секции `formatters`
- Настройте уровни логирования в секции `handlers`
- Добавьте дополнительные handlers (например, RotatingFileHandler, SysLogHandler)

Подробнее: https://docs.python.org/3/library/logging.config.html#logging-config-dictschema

### `prompts.md`

Пример файла с промптами в формате `.md` (Markdown).

**Формат:**

- Промпты разделяются строкой `---`
- Первый блок до разделителя — метаданные (пропускается)
- Пустые строки между промптами допускаются

**Использование:**

```bash
# Запустить напрямую
prompter examples/prompts.md -o hello-results.json

# Или создать свой файл на основе примера
cp examples/prompts.md my-tasks.md
nano my-tasks.md
prompter my-tasks.md
```

## Другие форматы

### `.adoc` (AsciiDoc)

```asciidoc
= Промпты для проекта
:doctype: article

Метаданные (первый блок пропускается)

'''

Первый промпт

'''

Второй промпт
```

### `.json` (JSON array)

```json
[
  "Первый промпт",
  {"$ref": "common/setup.json"},
  "Третий промпт"
]
```

## Смотрите также

- Основной README: `../README.md`
- Документация по тестам: `../tests/README.md`
- Спецификации: `../specs/`
