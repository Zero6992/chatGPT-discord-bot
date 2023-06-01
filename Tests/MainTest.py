import unittest
from unittest.mock import patch, MagicMock, PropertyMock, mock_open
import pkg_resources
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # previous directory
from main import *


class MainTest(unittest.TestCase):

    def setUp(self):

        # Create a list of stub packages
        with open('../requirements.txt') as f:
            self.fread = f.read()

        stub_required = self.fread.splitlines()

        stub_packages = []
        for i in range(len(stub_required)):
            package_name, package_version = stub_required[i].split('==')
            stub_packages.append(
                pkg_resources.Distribution(project_name=package_name, version=package_version))

        self.stub_packages = stub_packages

    @patch.object(pkg_resources, 'get_distribution')
    def test_check_version(self, mock_get_distribution):
        print("\n==== Testing check_version ====")

        mock_logger = MagicMock()

        # Patch the setup_logger function to return the mock logger
        with patch('src.log.setup_logger', return_value=mock_logger):
            with patch("main.open", mock_open(read_data=self.fread)) as mock_file:
                # Patch the sys.exit function to return a SystemExit exception
                with patch('sys.exit', side_effect=SystemExit) as mock_exit:
                    # mock_get_distribution will return the stub_packages list
                    mock_get_distribution.side_effect = self.stub_packages

                    check_version()

                    # assert that the file was opened correctly
                    mock_file.assert_called_once_with('requirements.txt')
                    with open("../requirements.txt") as f:
                        self.assertEqual(f.read(), self.fread)

                    mock_logger.error.assert_not_called()
                    mock_exit.assert_not_called()

    @patch.object(pkg_resources,
                  'get_distribution',
                  return_value=pkg_resources.Distribution(project_name='discord.py',
                                                          version='1.2.3'))
    def test_check_version_error(self, mock_get_distribution):
        print("\n==== Testing check_version with error ====")

        mock_logger = MagicMock()

        with patch('src.log.setup_logger', return_value=mock_logger):
            with patch("main.open", mock_open(read_data=self.fread)) as mock_file:
                with self.assertRaises(SystemExit) as cm:
                    check_version()

                mock_logger.error.assert_called_once_with(
                    'discord.py version 1.2.3 is installed but does not match the requirements')
                self.assertEqual(cm.exception.code, None)


if __name__ == '__main__':
    unittest.main(verbosity=2)  # pragma: no cover
