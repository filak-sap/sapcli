#!/usr/bin/env python3

import unittest

import sap.adt

from mock import Connection, Response

from fixtures_sap_adt_enhancement_spot import (
    FIXTURE_ADT_ENHS_REPOSITORY_ROOT,
    FIXTURE_ADT_ENHS_REPOSITORY_EHNO,
    FIXTURE_ADT_ENHS_REPOSITORY_BADI_DEFINITIONS,
)


def repository_response(text):
    return Response(
        status_code=200,
        text=text,
        content_type='application/vnd.sap.as+xml;charset=UTF-8;dataname=com.sap.adt.RepositoryObjectTreeContent'
    )


class TestEnhancementSpotGetImplementations(unittest.TestCase):

    def test_get_implementations_returns_names(self):
        connection = Connection([
            repository_response(FIXTURE_ADT_ENHS_REPOSITORY_ROOT),
            repository_response(FIXTURE_ADT_ENHS_REPOSITORY_EHNO),
        ])

        enhs = sap.adt.EnhancementSpot(connection, 'SSAMPLE_ENHS')

        self.assertEqual(enhs.get_implementations(),
                         ['MY_FABULOUS_ENHS_ONE', 'OPEN_SOURCE_IS_BEST'])

    def test_get_implementations_reads_the_right_nodes(self):
        connection = Connection([
            repository_response(FIXTURE_ADT_ENHS_REPOSITORY_ROOT),
            repository_response(FIXTURE_ADT_ENHS_REPOSITORY_EHNO),
        ])

        enhs = sap.adt.EnhancementSpot(connection, 'SSAMPLE_ENHS')
        enhs.get_implementations()

        self.assertEqual(connection.mock_methods(),
                         [('POST', '/sap/bc/adt/repository/nodestructure'),
                          ('POST', '/sap/bc/adt/repository/nodestructure')])

        self.assertEqual(connection.execs[0].params,
                         {'parent_name': 'SSAMPLE_ENHS',
                          'parent_tech_name': 'SSAMPLE_ENHS',
                          'parent_type': 'ENHS/XSB',
                          'withShortDescriptions': 'false'})

        self.assertIn('<TV_NODEKEY>000000</TV_NODEKEY>', connection.execs[0].body)
        self.assertIn('<TV_NODEKEY>000004</TV_NODEKEY>', connection.execs[1].body)

    def test_get_implementations_no_enho_node(self):
        connection = Connection([
            repository_response(FIXTURE_ADT_ENHS_REPOSITORY_BADI_DEFINITIONS),
        ])

        enhs = sap.adt.EnhancementSpot(connection, 'SSAMPLE_ENHS')

        self.assertEqual(enhs.get_implementations(), [])
        self.assertEqual(connection.mock_methods(),
                         [('POST', '/sap/bc/adt/repository/nodestructure')])

    def test_get_implementations_empty_enho_node(self):
        connection = Connection([
            repository_response(FIXTURE_ADT_ENHS_REPOSITORY_ROOT),
            repository_response(''),
        ])

        enhs = sap.adt.EnhancementSpot(connection, 'SSAMPLE_ENHS')

        self.assertEqual(enhs.get_implementations(), [])


if __name__ == '__main__':
    unittest.main()
