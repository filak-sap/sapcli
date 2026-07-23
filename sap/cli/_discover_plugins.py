"""Infrastructure for discovering plugins in the sap.cli.plugins package."""


import os
import os.path
import sys
import importlib.util
from typing import List


class PluginDefinitions(type):
    """Base class used to for discovering plugins. All plugin classes must inherit from this class."""

    loaded_plugins: List[type] = []

    def __init__(cls, name, _, __):
        super().__init__(cls)

        if name.startswith('APluginBase'):
            return

        PluginDefinitions.loaded_plugins.append(cls)


def _discover_plugins():
    """Load python modules from the plugins directory to make sure the plugins
       class constructors get called and return a list of plugin classes.
    """

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
