'''
Copyright 2016, EMC, Inc.

Author(s):
George Paulos

This script initializes RackHD stack after install.
    - loads SKU packs
    - loads default SKU
    - sets auth user
    - restarts nodes for discovery
    - discovers switches and/or PDUs if available
    - checks node discovery
    - assigns node OBM settings
    - checks pollers for data

'''


import os
import sys
import subprocess
# set path to common libraries
sys.path.append(subprocess.check_output("git rev-parse --show-toplevel", shell=True).rstrip("\n") + "/test/fit_tests/common")
import fit_common
import pdu_lib

# Locals
MAX_CYCLES = 60

class rackhd_stack_init(fit_common.unittest.TestCase):
    def test01_preload_sku_packs(self):
        print "**** Processing SKU Packs"
        # Load SKU packs from GutHub
        subprocess.call("rm -rf temp.sku; rm -rf on-skupack", shell=True)
        os.mkdir("on-skupack")
        # download all SKU repos and merge into on-skupack
        for url in fit_common.GLOBAL_CONFIG['repos']['skupack']:
            print "**** Cloning SKU Packs from " + url
            subprocess.call("git clone " + url + " temp.sku", shell=True)
            subprocess.call('cp -R temp.sku/* on-skupack; rm -rf temp.sku', shell=True)
        # build build SKU packs
        for subdir, dirs, files in os.walk('on-skupack'):
            for skus in dirs:
                if skus not in ["debianstatic", ".git"] and os.path.isfile('on-skupack/' + skus + '/config.json'):
                    subprocess.call("cd on-skupack;mkdir -p " + skus + "/tasks " + skus + "/static "
                                    + skus + "/workflows " + skus + "/templates", shell=True)
                    subprocess.call("cd on-skupack; ./build-package.bash "
                                    + skus + " " + skus + " >/dev/null 2>&1", shell=True)
            break
        # upload SKU packs to ORA
        print "**** Loading SKU Packs to server"
        for subdir, dirs, files in os.walk('on-skupack/tarballs'):
            for skupacks in files:
                print "\n**** Loading SKU Pack for " + skupacks
                fit_common.rackhdapi("/api/2.0/skus/pack", action="binary-post",
                                     payload=file(fit_common.TEST_PATH + "on-skupack/tarballs/" + skupacks).read())
            break
        print "\n"
        # check SKU directory against source files
        errorcount = ""
        skulist = fit_common.json.dumps(fit_common.rackhdapi("/api/2.0/skus")['json'])
        for subdir, dirs, files in os.walk('on-skupack'):
            for skus in dirs:
                if skus not in ["debianstatic", ".git", "packagebuild", "tarballs"] and os.path.isfile('on-skupack/' + skus + '/config.json'):
                    try:
                        fit_common.json.loads(open("on-skupack/" + skus  + "/config.json").read())
                    except:
                        print "FAILURE - Corrupt SKU config: " + configfile['name']
                        errorcount += "  Corrupt SKU config: " + configfile['name']
                    else:
                        configfile = fit_common.json.loads(open("on-skupack/" + skus  + "/config.json").read())
                        if configfile['name'] not in skulist:
                            print "FAILURE - Missing SKU: " + configfile['name']
                            errorcount += "  Missing SKU: " + configfile['name']
            break
        self.assertEqual(errorcount, "", errorcount)

    def test02_preload_default_sku(self):
        # Load default SKU for unsupported compute nodes
        print '**** Installing default SKU'
        payload = {
                        "name": "Unsupported-Compute",
                        "rules": [
                            {
                                "path": "bmc.IP Address"
                            }
                        ]
                    }
        api_data = fit_common.rackhdapi("/api/2.0/skus", action='post', payload=payload)
        self.assertEqual(api_data['status'], 201, 'Incorrect HTTP return code, expecting 201, got '
                         + str(api_data['status']))

    def test03_set_auth_user(self):
        print '**** Installing default admin user'
        fit_common.remote_shell('rm auth.json')
        auth_json = open('auth.json', 'w')
        auth_json.write('{"username":"' + fit_common.GLOBAL_CONFIG["api"]["admin_user"] + '", "password":"' + fit_common.GLOBAL_CONFIG["api"]["admin_pass"] + '", "role":"Administrator"}')
        auth_json.close()
        fit_common.scp_file_to_ora('auth.json')
        rc = fit_common.remote_shell("curl -ks -X POST -H 'Content-Type:application/json' https://localhost:" + str(fit_common.GLOBAL_CONFIG['ports']['https']) + "/api/2.0/users -d @auth.json" )
        if rc['exitcode'] != 0:
            print "ALERT: Auth admin user not set! Please manually set the admin user account if https access is desired."

    def test04_power_on_nodes(self):
        # This powers on nodes via PDU or, if no PDU, power cycles nodes via IPMI to start discovery
        # ServerTech PDU case
        if pdu_lib.check_pdu_type() != "Unknown":
            print '**** PDU found, powering on PDU outlets'
            self.assertTrue(pdu_lib.pdu_control_compute_nodes("on"), 'Failed to power on all outlets')
            # Wait about 30 seconds for the outlets to all come on and nodes to DHCP
            fit_common.countdown(30)
        # no PDU case
        else:
            print '**** No supported PDU found, restarting nodes using IMPI.'
            # Power off all nodes
            self.assertNotEqual(fit_common.power_control_all_nodes("off"), 0, 'No BMC IP addresses found')
            # Power on all nodes
            self.assertNotEqual(fit_common.power_control_all_nodes("on"), 0, 'No BMC IP addresses found')

    # Optionally install control switch node if present
    @fit_common.unittest.skipUnless("control" in fit_common.STACK_CONFIG[fit_common.ARGS_LIST['stack']],"")
    def test05_discover_control_switch_node(self):
        print "**** Creating control switch node."
        payload = {
                    "type": "switch",
                    "name": "Control",
                    "autoDiscover": "true",
                    "snmpSettings":{
                        "host": fit_common.STACK_CONFIG[fit_common.ARGS_LIST['stack']]['control'],
                        "community": fit_common.GLOBAL_CONFIG['snmp']['community'],
                    }
                    }
        api_data = fit_common.rackhdapi("/api/2.0/nodes", action='post', payload=payload)
        self.assertEqual(api_data['status'], 201, 'Incorrect HTTP return code, expecting 201, got '
                         + str(api_data['status']))

    # Optionally install data switch node if present
    @fit_common.unittest.skipUnless("data" in fit_common.STACK_CONFIG[fit_common.ARGS_LIST['stack']], "")
    def test06_discover_data_switch_node(self):
        print "**** Creating data switch node."
        payload = {
                    "type": "switch",
                    "name": "Data",
                    "autoDiscover": "true",
                    "snmpSettings":{
                        "host": fit_common.STACK_CONFIG[fit_common.ARGS_LIST['stack']]['data'],
                        "community": fit_common.GLOBAL_CONFIG['snmp']['community'],
                    }
                    }
        api_data = fit_common.rackhdapi("/api/2.0/nodes", action='post', payload=payload)
        self.assertEqual(api_data['status'], 201, 'Incorrect HTTP return code, expecting 201, got '
                         + str(api_data['status']))

    # Optionally install PDU node if present
    @fit_common.unittest.skipUnless("pdu" in fit_common.STACK_CONFIG[fit_common.ARGS_LIST['stack']], "")
    def test07_discover_pdu_node(self):
        print "**** Creating PDU node."
        payload = {
                    "type": "pdu",
                    "name": "PDU",
                    "autoDiscover": "true",
                    "snmpSettings":{
                        "host": fit_common.STACK_CONFIG[fit_common.ARGS_LIST['stack']]['pdu'],
                        "community": fit_common.GLOBAL_CONFIG['snmp']['community'],
                    }
                    }
        api_data = fit_common.rackhdapi("/api/2.0/nodes/", action='post', payload=payload)
        self.assertEqual(api_data['status'], 201, 'Incorrect HTTP return code, expecting 201, got '
                         + str(api_data['status']))

    def test08_check_compute_nodes(self):
        print "**** Waiting for compute nodes."
        c_index = 0
        for c_index in range(0, MAX_CYCLES):
            if "compute" in fit_common.rackhdapi("/api/2.0/nodes")['text']:
                break
            else:
                fit_common.time.sleep(30)
        self.assertLess(c_index, MAX_CYCLES-1, "No compute nodes found.")

    def test09_check_discovery(self):
        print "**** Waiting for node Discovery to complete.\n",
        # Determine if there are any active workflows. If returned value is true, obmSettings, SKUs
        # and active workflows are all either present or complete. If  the returned is false,
        # there was a timeout and all nodes have not obtained obmSetting, SKUs, or all active
        # workflows have not completed.
        # Wait 10 minutes ( MAX_CYCLES * 10 seconds) for this to occur.
        self.assertTrue(self.check_for_active_workflows(MAX_CYCLES), "Node discovery not completed")
        
    def check_for_active_workflows(self, max_time):
        '''
        Determine if are any active workflows.
        :param    Time to wait (in 10 second intervals)
        :return:  True  - No active workflows
                  False - Workflows are active
        '''
        for dummy in range(0, max_time):
            nodes_data = fit_common.rackhdapi("/api/2.0/nodes")
            if nodes_data['status'] == 200 and len(nodes_data['json']) > 0:
                # if there are nodes present, determine if discovery has completed on them
                discovery_complete = True
                for node in nodes_data['json']:
                    if node['type'] == 'compute':
                        self.assertIn('id', node, 'node does not contain id')
                        node_id = node['id']
                        # determine if there are any active worlflows. If so, discovery not completed
                        if fit_common.check_active_workflows(node_id):
                            discovery_complete = False
                            break
                if discovery_complete:
                    return True
                fit_common.time.sleep(10)
        return False

    def test10_apply_obm_settings(self):
        print "**** Apply OBM setting to compute nodes."
        self.assertTrue(fit_common.apply_obm_settings(), "OBM settings failed.")

    @fit_common.unittest.skipUnless("bmc" in fit_common.STACK_CONFIG[fit_common.ARGS_LIST['stack']],"")
    @fit_common.unittest.skip("Skipping 'test10_add_management_server' code incomplete")
    def test11_add_management_server(self):
        print "**** Creating management server."
        usr = ""
        pwd = ""
        # find correct BMC passwords from global config
        for creds in fit_common.GLOBAL_CONFIG['credentials']['bmc']:
            if fit_common.remote_shell('ipmitool -I lanplus -H ' + fit_common.ARGS_LIST['bmc']
                                   + ' -U ' + creds['username'] + ' -P '
                                   + creds['password'] + ' fru')['exitcode'] == 0:
                usr = creds['username']
                pwd = creds['password']
        # create management node using these creds
        payload = {
                    "name": "Management Server",
                    "type": "mgmt",
                    "autoDiscover": "true",
                    "ipmi-obm-service": {
                        "host": fit_common.ARGS_LIST['bmc'],
                        "user": usr,
                        "password": pwd
                    }
                    }
        api_data = fit_common.rackhdapi("/api/2.0/nodes", action='post', payload=payload)
        self.assertEqual(api_data['status'], 201, 'Incorrect HTTP return code, expecting 201, got '
                         + str(api_data['status']))
        # run discovery workflow
        payload = {
                    "name": "Graph.MgmtSKU.Discovery",
                    "options":{"defaults": {"nodeId": api_data['json']['id']}}
                    }
        api_data = fit_common.rackhdapi("/api/2.0/nodes/" + api_data['json']['id'] + "/workflows",
                                        action='post', payload=payload)
        self.assertEqual(api_data['status'], 201, 'Incorrect HTTP return code, expecting 201, got '
                         + str(api_data['status']))

    def test12_check_pollers(self):
        print "**** Waiting for pollers."
        # Determine if there are any pollers present. If the return value is true, there are pollers
        # active. If the return value is false, pollers are not active.
        # Wait 10 minutes ( MAX_CYCLES * 10 seconds) for this to occur.
        self.assertTrue(self.check_for_active_pollers(MAX_CYCLES), 'No pollers')
        print "**** Waiting for pollers data."
        # Determine if all the pollers have data. If the return value is true, all pollers have data
        # If the return value is false, poller are working but not collecting data.
        # Wait 10 minutes ( MAX_CYCLES * 10 seconds) for this to occur.
        self.assertTrue(self.check_for_active_poller_data(MAX_CYCLES), 'All pollers are not active')

    def check_for_active_pollers(self, max_time):
        '''
        Determine if all poller are active.
        :param    Time to wait (in 10 second intervals)
        :return:  True  - Poller active
                  False - Pollers not active
        '''
        for dummy in range(0, max_time):
            api_data = fit_common.rackhdapi('/api/2.0/pollers')
            if len(api_data['json']) > 0:
                return True
            fit_common.time.sleep(30)
        return False


    def check_for_active_poller_data(self, max_time):
        '''
        Determine if all poller have data.
        :param    Time to wait (in 10 second intervals)
        :return:  True  - Poller have data
                  False - Not all poller have data
        '''
        poller_list = []
        api_data = fit_common.rackhdapi('/api/2.0/pollers')
        if api_data:
            # set up a list of poller ids
            for index in api_data['json']:
                poller_list.append(index['id'])
            if poller_list != []:
                for dummy in range(0, max_time):
                    # move backwards through the list allowing completed poller ids to be popped 
                    # off the list
                    for i in reversed(range(len(poller_list))):
                        id = poller_list[i]
                        poll_data = fit_common.rackhdapi("/api/2.0/pollers/" + id + "/data/current")
                        # Check if data current returned 200 and data in the poll, if so, remove from list
                        if poll_data['status'] == 200 and len(poll_data['json']) != 0:
                            poller_list.pop(i)
                    if poller_list == []:
                        # return when all pollers look good
                        return True
                    fit_common.time.sleep(10)
        if poller_list != []:
            print "Poller IDs with error or no data: {}".format(fit_common.json.dumps(poller_list, indent=4))
        return False

if __name__ == '__main__':
    fit_common.unittest.main()
