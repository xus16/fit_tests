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

def get_switches():
    # returns a list with valid node IDs that match ARGS_LIST.sku in 'Name' or 'Model' field
    # and matches node BMC MAC address in ARGS_LIST.obmmac if specified
    # Otherwise returns list of all IDs that are not 'Unknown' or 'Unmanaged'
    nodelist = []

    # check if user specified a single nodeid to run against
    # user must know the nodeid and any check for a valid nodeid is skipped
    nodeid = fit_common.ARGS_LIST['nodeid']
    if nodeid != 'None':
        nodelist.append(nodeid)
    else:
        catalog = fit_common.rackhdapi('/api/2.0/nodes')
        for nodeentry in catalog['json']:
            if nodeentry['type'] == 'switch':
                nodelist.append(nodeentry['id'])
    return nodelist

class refresh_switch_nodes(fit_common.unittest.TestCase):

    def test_refresh_switch_nodes(self):
        # successful test here
        switchlist = get_switches()
        for switch in switchlist:
            payload = {
                "name":"Graph.Switch.Discovery",
                "options":{"create-switch-snmp-pollers":{"nodeId": switch}}
            }
            fit_common.rackhdapi("/api/2.0/nodes/" + switch + "/workflows", action="post", payload=payload)

if __name__ == '__main__':
    fit_common.unittest.main()
