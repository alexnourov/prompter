"""CLI-интерфейс для Prompter."""

import logging
from pathlib import Path
from typing import Annotated, Any

import typer

from prompter.config import find_config_dir, load_settings, setup_logging
from prompter.io import PromptReader, SessionLogger
from prompter.runner import ClaudeRunner

app = typer.Typer(
    name="prompter",
    help="CLI-утилита для автоматизации работы с Claude CLI.",
)

logger = logging.getLogger(__name__)


def _resolve_setting(
    cli_value: Any,
    settings: dict[str, Any],
    key: str,
    default: Any,
) -> Any:
    """Определяет значение настройки по приоритету: CLI > Settings > Default."""
    if cli_value is not None:
        return cli_value
    return settings.get(key, default)


@app.command()
def main(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Путь к файлу с промптами (.txt, .md или .json).",
            exists=True,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output", "-o",
            help="Путь к файлу отчёта.",
        ),
    ] = Path("report.json"),
    verbose: Annotated[
        bool | None,
        typer.Option(
            "--verbose", "-v",
            help="Включить подробный вывод.",
        ),
    ] = None,
    app_name: Annotated[
        str,
        typer.Option(
            "--app-name",
            help="Имя приложения для поиска конфигурации.",
        ),
    ] = "prompter",
    config: Annotated[
        Path | None,
        typer.Option(
            "--config", "-c",
            help="Путь к директории конфигурации.",
        ),
    ] = None,
) -> None:
    """Запускает промпты из файла через Claude CLI."""
    # Загрузка конфигурации
    config_dir = find_config_dir(app_name, config)
    settings = load_settings(config_dir)

    # Применение приоритетов настроек
    verbose_resolved = _resolve_setting(verbose, settings, "verbose", False)
    output_resolved = _resolve_setting(None, settings, "output", output)
    if isinstance(output_resolved, str):
        output_resolved = Path(output_resolved)

    # Настройка логирования
    setup_logging(config_dir, verbose=verbose_resolved)

    logger.info("Prompter запущен")
    logger.debug("Конфигурация: %s", config_dir)
    logger.debug("Настройки: %s", settings)

    # Создание компонентов
    runner = ClaudeRunner()
    reader = PromptReader()
    session_logger = SessionLogger()

    # Чтение промптов
    try:
        prompts = reader.read(input_file)
    except (FileNotFoundError, ValueError) as e:
        logger.error("Ошибка чтения промптов: %s", e)
        raise typer.Exit(code=1) from e

    total = len(prompts)
    logger.info("Загружено промптов: %d", total)

    # Цикл выполнения
    report: list[dict[str, Any]] = []

    for idx, prompt_text in enumerate(prompts, start=1):
        logger.info("Processing prompt %d/%d...", idx, total)

        try:
            result = runner.run_prompt(prompt_text)
        except KeyboardInterrupt:
            answer = typer.prompt("Interrupted. (N)ext or (E)xit?", default="E")
            if answer.upper() == "N":
                logger.info("Пропуск промпта %d", idx)
                continue
            else:
                logger.info("Прерывание по запросу пользователя")
                break
        except ValueError as e:
            logger.error("Ошибка выполнения промпта %d: %s", idx, e)
            result = {"error": str(e)}

        report.append({
            "prompt_index": idx,
            "prompt": prompt_text,
            "response": result,
        })

        if verbose_resolved:
            logger.debug("Результат промпта %d: %s", idx, result)

    # Сохранение отчёта
    session_logger.save_report(report, output_resolved)
    logger.info("Выполнение завершено. Отчёт: %s", output_resolved)


if __name__ == "__main__":
    app()
