#!/usr/bin/env python3

import mock
import uuid
import yaml
import unittest

from time import sleep
from pprint import pprint

import googleapiclient.discovery as googleapi
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

    def __init__(self, *args, **kwargs):
        super(__class__, self).__init__(*args, **kwargs)

        self.project = 'gbsc-gcp-project-scgs-dev'
        self.zone = 'us-central1-a'
        self.machine_type = 'n1-standard-1'
        self.name = 'sprout-test-instance'
        self.image_name = 'sprout-test-image'

        self.credentials = GoogleCredentials.get_application_default()
        self.compute = googleapi.build(
                                       'compute', 
                                       'v1', 
                                       credentials = self.credentials)

    def set_up(self, compute, project, zone, machine_type, name):
        """ Create basic compute instance in SCGS dev project.

        Run to set up environment to test GIMS deployment functions.

        Dev status: Done.

        compute (obj): Google compute API service client
        project (str): Google project ID
        zone (str): Compute zone ("us-west1-a")
        machine_type (str): Compute instance machine type
        name (str): Compute instance name
        """

        # Get the latest Debian Jessie image.
        image_response = compute.images().getFromFamily(
            project='debian-cloud', family='debian-8').execute()
        source_disk_image = image_response['selfLink']
        
        # Configure instance settings
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

        # Delete an existing disk image
        request_id = str(uuid.uuid4())
        request = self.compute.images().delete(
                                               project = self.project,
                                               image = self.image_name,
                                               requestId = request_id)
        try:
            response = request.execute()
            wait_for_status(request, response, 'DONE', 60)
        except HttpError as err:
            if err.resp.status in [404]:
                pprint("Skipping delete: image does not exist")
                pass
            else:
                raise

        # Delete an existing instance
        request_id = str(uuid.uuid4())
        request = self.compute.instances().delete(
                                             project = self.project,
                                             zone = self.zone,
                                             instance = self.name,
                                             requestId = request_id)
        try:
            response = request.execute()
            wait_for_status(request, response, 'DONE', 300)
        except HttpError as err:
                if err.resp.status in [404]:
                    pprint("Skipping delete: instance does not exist")
                    pass
                else:
                    raise

        # Create new instance
        request_id = str(uuid.uuid4())
        request = self.compute.instances().insert(
                                                  project = self.project,
                                                  zone = self.zone,
                                                  body = config,
                                                  requestId = request_id)
        response = request.execute()
        wait_for_status(request, response, 'DONE', 300)
        pprint("Setup complete.")
        pprint("=================")

    def test_stop_instance(self):
        """ Stop compute instance.

        Dev status: Done.
        """
        pprint("Setting up compute instance.")
        self.set_up(
                    self.compute,
                    self.project,
                    self.zone,
                    self.machine_type,
                    self.name)
        pprint("Setup complete.")

        ComputeOperations.stop_instance(
                                        self.compute, 
                                        self.project, 
                                        self.zone, 
                                        self.name)

        # Check that instance has been stopped
        request = self.compute.instances().get(
                                               project = self.project,
                                               zone = self.zone,
                                               instance = self.name)
        response = request.execute()
        self.assertTrue(response['status'] == 'TERMINATED')

    def test_delete_instance(self):
        """ Delete compute instance.

        Dev status: Done.
        """
        pprint("Setting up compute instance.")
        self.set_up(
                    self.compute,
                    self.project,
                    self.zone,
                    self.machine_type,
                    self.name)
        pprint("Setup complete.")

        ComputeOperations.delete_instance(
                                          self.compute, 
                                          self.project, 
                                          self.zone, 
                                          self.name)

        # Get list of comute instances
        request = self.compute.instances().list(
                                                project = self.project,
                                                zone = self.zone)
        response = request.execute()
        
        # Determine whether instance is in list
        for instance in response['items']:
            self.assertFalse(instance['name'] == self.name)

    def test_create_image(self):
        """ Stop instance and create image from it.

        Dev status: Done.
        """
        source_disk = "zones/{}/disks/{}".format(
                                                 self.zone,
                                                 self.name)
        force = True

        pprint("Setting up compute instance.")
        self.set_up(
                    self.compute,
                    self.project,
                    self.zone,
                    self.machine_type,
                    self.name)

        ComputeOperations.stop_instance(
                                        self.compute, 
                                        self.project, 
                                        self.zone, 
                                        self.name)
        ComputeOperations.create_image(
                                       compute = self.compute, 
                                       project = self.project, 
                                       image_name = self.image_name, 
                                       source_disk = source_disk, 
                                       force = True)
        # Test whether you can get image
        request = self.compute.images().get(
                                            project = self.project,
                                            image = self.image_name)
        try:
            response = request.execute()
        except HttpError as err:
            pprint(response)

    def test_delete_image(self):
        """ Delete disk image.

        Dev status: In-progress.
        """
        ComputeOperations.delete_image(
                                       compute = self.compute,
                                       project = self.project,
                                       image_name = self.image_name)
        # Get list of images
        # Make sure this one is not in it

    """
    def test_deprecate_image(self):
    """

class ParseArgsTestCase(unittest.TestCase):

    def test_config_arg(self):
        args = parse_args(['--config', 'sprout_unittest.yaml'])
        self.assertTrue(args.config_file == "sprout_unittest.yaml")


def wait_for_status(request, response, status, timeout):
    """ Wait for Google Cloud API request to complete.

    Possible status are PENDING, RUNNING, or DONE.
    """

    sleep_interval = 5
    timeout_cycles = int(timeout)/sleep_interval

    valid_statuses = ['PENDING', 'RUNNING', 'DONE']
    if not status in valid_statuses:
        raise ValueError(
                         '{} '.format(status) + 
                         'is not a valid status. ' + 
                         '{}'.format(valid_statuses))

    # TODO: Test custom error and fully integrate status/timeout 
    # variables into function.
    n = 0
    while response['status'] != status:
        if n >= timeout_cycles:
            raise TimeoutError("Operation exceeded timeout period. " +
                               "{}: {}".format(op_kind, op_type))
        sleep(sleep_interval)
        response = request.execute()
        op_kind = response['kind']
        op_type = response['operationType']
        pprint("Waiting for operation. {}: {}".format(
                                                      op_kind,
                                                      op_type))
    pprint("=================")
    pprint("Operation complete. {}: {}.".format(
                                               op_kind,
                                               op_type))
    pprint("=================")


if __name__ == '__main__':
    unittest.main()


