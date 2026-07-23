"""Some useful commands for FLP"""

import json
from html.parser import HTMLParser

import sap.cli.core
import sap.cli.plugin


class FlpPlugin(sap.cli.plugin.APluginBaseFLP):

    def command_group(self):
        return CommandGroup()


class CommandGroup(sap.cli.core.CommandGroup):
    """Container for user commands."""

    def __init__(self):
        super().__init__('fiori')


class FlpHtmlParser(HTMLParser):
    """ADT Object XML parser"""

    def __init__(self):
        super().__init__()

        self.assignedSpaces = None

    def handle_starttag(self, name, attrs):
        if name != 'meta':
            return

        isSpaces = False
        spaces = None
        for attr, value in attrs:
            if attr == 'name' and value == 'sap.ushell.assignedSpaces':
                isSpaces = True

            if attr == 'content':
                spaces = value

        if isSpaces:
            self.assignedSpaces = json.loads(spaces)


@CommandGroup.command('list-spaces')
# pylint: disable=unused-argument
def list_spaces(connection, args):
    """List FLP apps"""

    resp = connection.execute("GET", 'bc/ui2/flp')
    body = resp.content.decode('utf-8')

    parser = FlpHtmlParser()
    parser.feed(body)

    if parser.assignedSpaces is None:
        print("No assigned spaces found")
        print(body)
        return

    for space in parser.assignedSpaces:
        print(f"{space['title']} :: {space['id']}")
        for page in space['pages']:
            print(f"  {page['title']} :: {page['id']} (visible: {page['visibility']['desktop']})")


@CommandGroup.command('list-apps')
# pylint: disable=unused-argument
def list_apps(connection, args):
    """List FLP apps"""

    params = {
        'so': '*',
        'action': '*',
        'systemAliasesFormat': 'object',
        'shellType': 'FLP',
        'depth': '0',
    }

    headers = {
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Priority': 'u=0, i',
    }

    try:
        resp = connection.execute("GET", 'bc/ui2/start_up', params=params, headers=headers)
    except Exception as err:
        print(f"Status : {err.response.status_code}")
        print(f"Message: {err.response.content}")
        return

    tiles = resp.json()
    mappings = tiles['targetMappings']

    for mapping, definition in mappings.items():
        text = 'n/a'
        if 'text' in definition:
            text = definition['text']
        print(f"{text} :: {mapping}")
