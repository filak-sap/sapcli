"""Enhancement Spot ADT wrappers"""

from typing import List

import sap.adt
from sap.adt.objects import (
    xmlns_adtcore_ancestor,
    ADTObject,
    ADTObjectType,
    ADTObjectPropertyEditor,
)


XMLNS_ENHS = xmlns_adtcore_ancestor('enhs', 'http://www.sap.com/adt/enhancements/enhs')


# Stub class because we currently need to only list enhancement implementations
class EnhancementSpot(ADTObject):
    """The ADT object Enhancement Spot"""

    OBJTYPE = ADTObjectType(
        'ENHS/XSB',
        'enhancements/enhsxsb',
        XMLNS_ENHS,
        ['application/vnd.sap.adt.enh.enhs.v2+xml'],
        {},
        'objectData',
        editor_factory=ADTObjectPropertyEditor
    )

    def __init__(self, connection, name, package=None, metadata=None):
        super().__init__(connection, name, metadata)

        self._metadata.package_reference.name = package

    def get_implementations(self) -> List[str]:
        """Get a list of enhancement implementation names for this enhancement spot"""

        repo = sap.adt.Repository(self._connection)
        node = repo.read_node(self, nodekeys=['000000'])
        enhs_node_key = None
        for typ in node.types:
            if typ.OBJECT_TYPE == sap.adt.EnhancementImplementation.OBJTYPE.code:
                enhs_node_key = typ.NODE_ID

        if enhs_node_key is None:
            return []

        impls = repo.read_node(self, nodekeys=[enhs_node_key])
        return [impl.OBJECT_NAME for impl in impls.objects]
