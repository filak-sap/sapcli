"""
ADT proxy for Enhancement Spots commands
"""

import sap.adt
import sap.cli.core


class CommandGroup(sap.cli.core.CommandGroup):
    """Commands for Enhancement Spots"""

    def __init__(self):
        super().__init__('enhs')


@CommandGroup.argument('enhancement_spot', help='Enhancement Spot Name')
@CommandGroup.command('list-implementations')
def list_implementations(connection, args):
    """List Enhancement Implementations of the given Enhancement Spot
    """

    console = args.console_factory()

    enhs = sap.adt.EnhancementSpot(connection, args.enhancement_spot)
    for impl in enhs.get_implementations():
        console.printout(f'{impl}')
