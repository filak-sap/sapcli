#!/usr/bin/env python3

import unittest
from unittest.mock import patch

import sap.cli.enhs

from mock import Connection, ConsoleOutputTestCase, PatcherTestCase

from infra import generate_parse_args


parse_args = generate_parse_args(sap.cli.enhs.CommandGroup())


class TestEnhsListImplementations(ConsoleOutputTestCase, PatcherTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        PatcherTestCase.__init__(self)

    def tearDown(self):
        try:
            PatcherTestCase.unpatch_all(self)
        finally:
            super().tearDown()

    def setUp(self):
        super().setUp()
        ConsoleOutputTestCase.setUp(self)

        self.patch_console(console=self.console)

    def test_list_implementations(self):
        with patch('sap.adt.EnhancementSpot.get_implementations') as mock_get:
            mock_get.return_value = ['MY_FABULOUS_ENHS_ONE', 'OPEN_SOURCE_IS_BEST']

            list_cmd = parse_args('list-implementations', 'SSAMPLE_ENHS')
            list_cmd.execute(None, list_cmd)

        self.assertConsoleContents(
            self.console,
            stdout='MY_FABULOUS_ENHS_ONE\nOPEN_SOURCE_IS_BEST\n')

    def test_list_implementations_empty(self):
        with patch('sap.adt.EnhancementSpot.get_implementations') as mock_get:
            mock_get.return_value = []

            list_cmd = parse_args('list-implementations', 'SSAMPLE_ENHS')
            list_cmd.execute(None, list_cmd)

        self.assertConsoleContents(self.console, stdout='')

    def test_list_implementations_passes_the_spot_name(self):
        connection = Connection()

        with patch('sap.adt.EnhancementSpot.get_implementations', return_value=[]) as mock_get:
            with patch('sap.cli.enhs.sap.adt.EnhancementSpot.__init__', return_value=None) as mock_init:
                list_cmd = parse_args('list-implementations', 'SSAMPLE_ENHS')
                list_cmd.execute(connection, list_cmd)

            mock_init.assert_called_once_with(connection, 'SSAMPLE_ENHS')
            mock_get.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
