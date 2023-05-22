import sap.cli.core

import sap.cli.plugin
from sap.cli.plugins.centralrepo.ddci import DdciRepoGroup


class CentralRepoPlugin(sap.cli.plugin.APluginBaseGcts):

    def command_group(self):
        return CommandGroup()


class CommandGroup(sap.cli.core.CommandGroup):
    """Adapter converting command line parameters to sap.rest.gcts
       methods calls.
    """
    def __init__(self):
        super().__init__('centralrepo')

        self.ddci_repo_grp = DdciRepoGroup()

    def install_parser(self, arg_parser):
        gcts_group = super().install_parser(arg_parser)

        ddci_repo_parser = gcts_group.add_parser(self.ddci_repo_grp.name)
        self.ddci_repo_grp.install_parser(ddci_repo_parser)
