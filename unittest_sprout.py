#!/usr/bin/env python3

import mock
import uuid
import yaml
import unittest

from time import sleep
from pprint import pprint

import googleapiclient.discovery
from googleapiclient.errors import HttpError
from oauth2client.client import GoogleCredentials

from sprout import parse_args
from sprout import TerraformDeployment
from sprout import ComputeOperations

class TestTerraformDeployment(unittest.TestCase):

    @mock.patch('sprout.call')
    def test_basic_tf_plan_call(self, mock_call):
        name = 'development'
        var_files = ['test.tfvars']
        state_file = 'tfstate-files/test.tfstate'
        #variables = {'version': '0.1'}

        basic_plan_call = [
                           "terraform",
                           "plan",
                           "-var-file={}".format(var_files[0]),
                           "-state={}".format(state_file)]

        deployment = TerraformDeployment(
                                         name = name,
                                         var_files = var_files, 
                                         state_file = state_file)
        deployment.plan(dry_run = False)
        mock_call.assert_called_with(basic_plan_call)

    def test_read_yaml_config(self):
        """ Test formatting of sprout config file.
        """
        config_file = 'sprout_unittest.yaml'

        with open(config_file) as config_fh:
            config = yaml.load(config_fh)
        self.assertTrue(len(config['terraform_sets']) == 1)

        dev_set = config['terraform_sets'][0]
        self.assertTrue(dev_set['name'] == 'development')
        self.assertTrue(dev_set['var-file'] == 'development.tfvars')
        self.assertTrue(dev_set['state-file'] == 'tfstate-files/development.tfstate')
            
class TestGimsDeployment(unittest.TestCase):

    def __init__(self):
        self.project = 'gbsc-gcp-project-scgs-dev'
        self.zone = 'us-central1-a'
        self.machine_type = 'n1-standard-1'
        self.name = 'sprout-test-instance'

        self.credentials = GoogleCredentials.get_application_default()
        self.compute = googleapiclient.discovery.build(
                                                  'compute', 
                                                  'v1', 
                                                  credentials = credentials)

    def set_up(self, compute, project, zone, machine_type, name):
        """ Create compute instance in SCGS dev project.

        Run to set up environment to test GIMS deployment functions.

        compute (obj): Google compute API service client
        project (str): Google project ID
        zone (str): Compute zone ("us-west1-a")
        machine_type (str): Compute instance machine type
        name (str): Compute instance name
        """

        #project = 'gbsc-gcp-project-scgs-dev'
        #zone = 'us-central1-a'
        #machine_type = 'n1-standard-1'
        #name = 'sprout-test-instance'

        # Get the latest Debian Jessie image.
        image_response = compute.images().getFromFamily(
            project='debian-cloud', family='debian-8').execute()
        source_disk_image = image_response['selfLink']
        
        # Create instance
        machine_url = "zones/{}/machineTypes/{}".format(
                                                        zone,
                                                        machine_type)
        config = {
            "name": name,
            "machineType": machine_url,

            # Specify the boot disk and the image to use as a source.
            'disks': [
                {
                    'boot': True,
                    'autoDelete': True,
                    'initializeParams': {
                        'sourceImage': source_disk_image,
                    }
                }
            ],

            # Specify a network interface with NAT to access the public
            # internet.
            'networkInterfaces': [{
                'network': 'global/networks/default',
                'accessConfigs': [
                    {
                     'type': 'ONE_TO_ONE_NAT', 
                     'name': 'External NAT'
                    }
                ]
            }]
        }

        # Delete instance
        try:
            request_id = str(uuid.uuid4())
            request = compute.instances().delete(
                                                 project = project,
                                                 zone = zone,
                                                 instance = name,
                                                 requestId = request_id)
            response = request.execute()
            wait_for_request(request, response)
        except HttpError as err:
                if err.resp.status in [404]:
                    pprint("Skipping delete: instance does not exist")
                    pass
                else:
                    raise
        # Wait for status to be complete

        # Create instance
        request_id = str(uuid.uuid4())
        request = compute.instances().insert(
                                             project = project,
                                             zone = zone,
                                             body = config,
                                             requestId = request_id)
        response = request.execute()
        wait_for_request(request, response)

    def test_stop_instance(self):
        self.set_up(
                    self.compute,
                    self.project,
                    self.zone,
                    self.machine_type,
                    self.name)
        stop_instance(self.project, self.zone, self.name)

        # Periodically check whether instance is stopped
        # After a fixed period, timeout with failure

    def test_delete_instance(self):

    def test_create_instance(self):

    def test_deprecate_image(self):

    def test_delete_image(self):

        

        ## Functions to test:
        # stop_instance
        # delete_instance
        # create_image
        # deprecate_image
        # delete_image


class ParseArgsTestCase(unittest.TestCase):

    def test_config_arg(self):
        args = parse_args(['--config', 'sprout_unittest.yaml'])
        self.assertTrue(args.config_file == "sprout_unittest.yaml")

def wait_for_status(request, response, status, int(timeout)):
    """ Wait for Google Cloud API request to complete.

    Possible status are PENDING, RUNNING, or DONE.
    """

    sleep_interval = 2
    timeout_cycles = timeout/sleep_interval

    # TODO: Test custom error and fully integrate status/timeout 
    # variables into function.
    n = 0
    while response['status'] != 'DONE':
        if n >= timeout_cycles:
            raise TimeoutError("Operation exceeded timeout period. " +
                               "{}: {}".format(op_kind, op_type))
            #pprint("Operation timed out.")
            #break
        sleep(2)
        response = request.execute()
        op_kind = response['kind']
        op_type = response['operationType']
        pprint("Waiting for operation. {}: {}".format(
                                                      op_kind,
                                                      op_type))
    pprint("Operation complete. {}: {}".format(
                                               op_kind,
                                               op_type))
    pprint("=================")

if __name__ == '__main__':
    unittest.main()


