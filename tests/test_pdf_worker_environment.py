import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from easyread import pdf_isolation, i18n


class FrozenWorkerEnvironmentTest(unittest.TestCase):
    def test_worker_can_resolve_a_home_without_account_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            process=Mock()
            process.communicate.return_value=(b'[]',b'')
            process.returncode=0
            process.poll.return_value=0
            with patch.object(sys,'frozen',True,create=True), patch.object(pdf_isolation,'_job',return_value=lambda:None), \
                 patch.object(pdf_isolation.subprocess,'Popen',return_value=process) as popen, \
                 patch.object(i18n,'lang',return_value='en'), \
                 patch.dict(os.environ,{'CODEX_HOME':'C:/Synthetic/account','OPENAI_API_KEY':'SYNTHETIC-NOT-A-KEY'}):
                self.assertEqual(pdf_isolation.run('prepare',root),[])
            env=popen.call_args.kwargs['env']
            self.assertEqual(env['EASYREAD_HOME'],str(root/'.worker-state'))
            self.assertEqual(env['HOME'],str(root))
            self.assertEqual(env['USERPROFILE'],str(root))
            self.assertEqual(env['EASYREAD_LANG'],'en')
            self.assertNotIn('CODEX_HOME',env)
            self.assertNotIn('OPENAI_API_KEY',env)
            self.assertEqual(env['PYINSTALLER_RESET_ENVIRONMENT'],'1')
