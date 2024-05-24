import click

from .extract_examples import extract_examples
from .extract_documentation import extract_documentation


@click.group()
def cli():
    """
    CLI Tooling to help build Bunsen contexts
    """
    pass

cli.add_command(extract_examples)
cli.add_command(extract_documentation)
