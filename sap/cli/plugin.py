"""Base classes for implementing CLI plugins"""

import sap.cli
from sap.cli._discover_plugins import PluginDefinitions


class APluginBase(metaclass=PluginDefinitions):
    """Any plugin should inherit from this class and implement the
       command_group and connection methods.
    """

    def command_group(self):
        """Return new instance of sap.cli.core.CommandGroup defining CLI interface of the plugin."""

        raise NotImplementedError

    def connection(self):
        """Any object your plugin needs to connect to (e.g. ADT, gCTS, Fiori Launchpad)."""

        raise NotImplementedError


class APluginBaseADT(metaclass=PluginDefinitions):
    """Any plugin should inherit from this class and implement the
       command_group method.

       The connection method is already implemented to
       return the ADT connection from the sap.cli module.
    """

    def command_group(self):
        """Return new instance of sap.cli.core.CommandGroup defining CLI interface of the plugin."""

        raise NotImplementedError

    def connection(self):
        """Any object your plugin needs to connect to (e.g. ADT, gCTS, Fiori Launchpad)."""

        return sap.cli.adt_connection_from_args


class APluginBaseGcts(metaclass=PluginDefinitions):
    """Any plugin should inherit from this class and implement the
       command_group method.

       The connection method is already implemented to
       return the gCTS/REST connection from the sap.cli module.
    """

    def command_group(self):
        """Return new instance of sap.cli.core.CommandGroup defining CLI interface of the plugin."""

        raise NotImplementedError

    def connection(self):
        """Any object your plugin needs to connect to (e.g. ADT, gCTS, Fiori Launchpad)."""

        return sap.cli.gcts_connection_from_args


class APluginBaseFLP(metaclass=PluginDefinitions):
    """Any plugin should inherit from this class and implement the
       command_group method.

       The connection method is already implemented to
       return the Fiori Launchpad connection from the sap.cli module.
    """

    def command_group(self):
        """Return new instance of sap.cli.core.CommandGroup defining CLI interface of the plugin."""

        raise NotImplementedError

    def connection(self):
        """Any object your plugin needs to connect to (e.g. ADT, gCTS, Fiori Launchpad)."""

        return sap.cli.flp_connection_from_args
