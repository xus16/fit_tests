'''
Copyright 2016, EMC, Inc.

Author(s):

FIT test script template
'''

import os
import sys
import subprocess

# set path to common libraries
sys.path.append(subprocess.check_output("git rev-parse --show-toplevel", shell=True).rstrip("\n") + "/test/fit_tests/common")
import fit_common

class refresh_compute_nodes(fit_common.unittest.TestCase):
    def test_refresh_compute_nodes(self):
        # successful test here
        nodelist = fit_common.node_select()
        for node in nodelist:
            payload = {
                "name":"Graph.Refresh.Immediate.Discovery",
                "options":{"create-default-pollers":{"nodeId": node}}
            }
            fit_common.rackhdapi("/api/2.0/nodes/" + node + "/workflows", action="post", payload=payload)

if __name__ == '__main__':
    fit_common.unittest.main()
