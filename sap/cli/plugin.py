import os
import sys
import os.path
import importlib.util

from typing import List

import sap.cli


def discover_plugins():
    plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plugins')
    for fileordir in os.listdir(plugin_dir):
        module_name = fileordir
        if module_name[0] in ['.', '_']:
            continue

        abspath = os.path.join(plugin_dir, fileordir)
        if abspath.endswith('.py'):
            module_name = fileordir[:-3]
        elif os.path.isdir(abspath):
            module_name = fileordir
            abspath = os.path.join(abspath, '__init__.py')
        else:
            continue

        abs_module_name = f'sap.cli.plugins.{module_name}'
        spec = importlib.util.spec_from_file_location(abs_module_name, abspath)
        module = importlib.util.module_from_spec(spec)
        sys.modules[abs_module_name] = module
        spec.loader.exec_module(module)

    return PluginDefinitions.loaded_plugins


class PluginDefinitions(type):
    loaded_plugins: List[type] = list()

    def __init__(cls, name, bases, attrs):
        super().__init__(cls)

        if name.startswith('APluginBase'):
            return

        PluginDefinitions.loaded_plugins.append(cls)


class APluginBase(object, metaclass=PluginDefinitions):

    def command_group(self):
        raise NotImplementedError

    def connection(self):
        raise NotImplementedError


class APluginBaseADT(object, metaclass=PluginDefinitions):

    def command_group(self):
        raise NotImplementedError

    def connection(self):
        return sap.cli.adt_connection_from_args


class APluginBaseGcts(object, metaclass=PluginDefinitions):

    def command_group(self):
        raise NotImplementedError

    def connection(self):
        return sap.cli.gcts_connection_from_args
