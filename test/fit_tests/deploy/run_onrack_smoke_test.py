'''
Copyright 2015, EMC, Inc.

Author(s):
George Paulos

This wrapper script installs OnRack and runs Smoke Test.
'''

import os
import sys
import subprocess
# set path to common libraries
sys.path.append(subprocess.check_output("git rev-parse --show-toplevel", shell=True).rstrip("\n") + "/test/fit_tests/common")
import fit_common

# Check for -template parameter for OnRack OVA
if fit_common.ARGS_LIST["template"] == fit_common.GLOBAL_CONFIG['repos']['install']['template']:
    print "ERROR: '-template' parameter required for path or URL to OnRack OVA."
    sys.exit(255)

class onrack_smoke_test(fit_common.unittest.TestCase):
    def test01_install_os_ova(self):
        self.assertEqual(fit_common.run_nose(fit_common.TEST_PATH + '/deploy/os_ova_install.py'), 0, 'OS installer failed.')

    def test02_initialize_stack(self):
        self.assertEqual(fit_common.run_nose(fit_common.TEST_PATH + '/deploy/onrack_stack_init.py'), 0, 'OnRack stack init failed.')

    def test03_onrack_smoke_test(self):
        # set test group to 'smoke'
        fit_common.ARGS_LIST['group'] = "smoke"
        self.assertEqual(fit_common.run_nose(fit_common.TEST_PATH + '/tests'), 0, 'OnRack Smoke Test failed.')

if __name__ == '__main__':
    fit_common.unittest.main()