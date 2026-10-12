import argparse
import unittest
from unittest.mock import patch

from easyread import cli


class LauncherTests(unittest.TestCase):
    def test_pythonw_reopens_existing_service_without_stdout(self):
        args = argparse.Namespace(port=None, open=True, exit_on_close=True)
        with patch.object(cli.sys, 'stdout', None), \
                patch.object(cli.config, 'temp_library', return_value=False), \
                patch.object(cli, 'running_server', return_value='http://127.0.0.1:8876'), \
                patch.object(cli.config, 'server_token', return_value='SYNTHETIC'), \
                patch('webbrowser.open') as browser:
            cli.cmd_serve(args)
        browser.assert_called_once_with('http://127.0.0.1:8876/auth?session=SYNTHETIC')
