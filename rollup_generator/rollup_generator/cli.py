import logging
import importlib.metadata
import pathlib

import click


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
