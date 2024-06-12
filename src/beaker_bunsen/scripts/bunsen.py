import os
from typing import List

import click

from .extract_examples import extract_examples
from .extract_documentation import extract_documentation


class BunsenCLI(click.Group):
    """
    Something something
    """

    def list_commands(self, ctx: click.Context) -> List[str]:
        # Move new and update to top of list of commands, let rest be sorted via default (alphabetical)
        commands = super().list_commands(ctx)
        commands.remove("new")
        commands.insert(0, "new")
        commands.remove("update")
        commands.insert(1, "update")
        return commands


@click.group(cls=BunsenCLI)
def cli_commands():
    """
    CLI Tooling to help build and maintain Bunsen contexts
    """
    pass


@cli_commands.command()
@click.argument("dest", required=False, type=click.Path(exists=False))
def new(dest=None):
    """
    Create a new Bunsen context via a wizard
    """
    if dest and os.path.exists(dest):
        if os.listdir(dest):
            raise click.BadParameter(
                "Destination directory exists but is not empty. Aborting.",
                param="dest",
                param_hint="destination must be empty"
            )
    click.echo("Coming soon...")


@cli_commands.command()
def update():
    """
    Check if a Bunsen context needs to be updated
    """




cli_commands.add_command(extract_examples)
cli_commands.add_command(extract_documentation)
