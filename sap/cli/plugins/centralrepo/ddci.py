"""gCTS methods"""

import os
import warnings

import sap.cli.core
import sap.cli.helpers
import sap.rest.gcts.simple


class DdciRepoGroup(sap.cli.core.CommandGroup):
    """Container for user commands."""

    def __init__(self):
        super().__init__('ddci')


@DdciRepoGroup.command('list')
# pylint: disable=unused-argument
def repolist(connection, args):
    """ls"""

    console = sap.cli.core.get_console()

    response = sap.rest.gcts.simple.fetch_repos(connection)

    columns = (
        sap.cli.helpers.TableWriter.Columns()
        ('name', 'Name')
        ('role', 'Role')
        ('branch', 'Branch', default='')
        ('status', 'Status')
        ('vsid', 'vSID')
        ('url', 'URL')
        .done()
    )

    ddci_repos = (repo for repo in response if any((f'/{org}/' in repo.url.lower() for org in ['s4core', 's4corehome', 'asabap'])))
    sap.cli.helpers.TableWriter(ddci_repos, columns).printout(console)

    return 0
