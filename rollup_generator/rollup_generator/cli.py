import logging
import importlib.metadata
import pathlib
import json

import click

from rollup_generator.validation_service import validate_entity_service

PATHS = {}

PATHS["logging_file"] = pathlib.Path("rollup-generator.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - [%(levelname)s] - %(filename)s - L%(lineno)d - %(message)s",
    handlers=[logging.FileHandler(PATHS["logging_file"]), logging.StreamHandler()],
)

logger = logging.getLogger()


@click.group()
def cli() -> None:
    logger.info(
        f"Running rollup-generator version: {importlib.metadata.version('rollup-generator')}"
    )


@cli.command()
def smoke_test() -> None:
    print("Run running, running")


@cli.command()
@click.argument(
    "json_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
def validate_entity_definition(json_path):
    with open(json_path, "r") as f:
        json_content = json.load(f)
    validate_entity_service(json_content)
    logger.info("Validation successful!")
