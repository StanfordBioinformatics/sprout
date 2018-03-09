#!/usr/bin/env python3

import sys
import hcl
import uuid
import yaml
import argparse

from time import sleep
from pprint import pprint
from subprocess import call

import googleapiclient.discovery
from oauth2client.client import GoogleCredentials

class TerraformDeployment:

    def __init__(self, name, state_file, var_files):
        """ Manage Terraform deployment process.

            name(str): Arbitrary name of this deployment process
            state_file(str): Path to tfstate file
            var_files(list): List of tfvars files
        """

        self.name = name
        self.state_file = state_file
        self.var_files = var_files

    def _launch(self, tf_command, dry_run):
        """ Launch Terraform deployment process.
        """
        arguments = ['terraform', tf_command]
        for var_file in self.var_files:
            arguments.append("-var-file={}".format(var_file))
        arguments.append("-state={}".format(self.state_file))
        if dry_run:
            print(arguments)
        else:
            call(arguments)

    def destroy(self, dry_run):
        """ Call Terraform with 'destroy' command.
        """
        self._launch(tf_command='destroy', dry_run=dry_run)

    def plan(self, dry_run):
        """ Call Terraform with 'plan' command.
        """
        self._launch(tf_command='plan', dry_run=dry_run)

    def apply(self, dry_run):
        """ Call Terraform with 'apply' command.
        """
        self._launch(tf_command='apply', dry_run=dry_run)

    def run(self, dry_run):
        """ Run full deployment pipeline.

        Run destroy and apply.
        """
        self.destroy()
        self.apply()

class GimsDeployment(TerraformDeployment):

    def __init__(self, compute, name, state_file, var_files):
        super().__init__(name, state_file, var_files)
        
        self.compute = compute
        self.vars = {}

        # Read data from tfvars files into dictionary
        for var_file in self.var_files:
            with open(var_file, 'r') as fh:
                new_vars = hcl.load(fh)
                self.vars.update(new_vars)

        #! This is not a scalable approach
        # This needs to be fixed
        self.project = self.vars['project']
        self.zone = self.vars['zone']
        self.load_balancer_vm = self.vars['load_balancer_vm']
        self.template_vm = self.vars['template_vm']
        self.image_name = self.vars['image_name']

    def run(self, dry_run):
        """ Run full deployment pipeline.
        """

        self.destroy()
        self.apply()

        compute = ComputeOperator(self.project, self.zone)

        compute.stop_instance(self.name)
        compute.delete_image()
        compute.create_image()
        compute.delete_instance()

class ComputeOperator:

    def __init__(self, project, zone):
        """ 

        Status: Untested.
        """

        self.project = project
        self.zone = zone
        
        self.credentials = GoogleCredentials.get_application_default()
        self.compute = googleapi.build(
                                       'compute', 
                                       'v1', 
                                       credentials = self.credentials)

    #@staticmethod
    def stop_instance(self, name):
        """ Stop a running GCP instance.

        Status: Tested.
        """
        request_id = str(uuid.uuid4())
        request = self.compute.instances().stop(
                                                project = self.project,
                                                zone = self.zone,
                                                instance = name,
                                                requestId = request_id)
        response = request.execute()
        wait_for_status(
                        request, 
                        response, 
                        status = 'DONE', 
                        interval = 10)

    #@staticmethod
    def delete_instance(self, name):
        """ Delete a GCP compute instance.

        Status: Untested.
        """
        request_id = str(uuid.uuid4())
        request = self.compute.instances().delete(
                                                  project = self.project,
                                                  zone = self.zone, 
                                                  instance = name,
                                                  requestId = request_id)
        response = request.execute()
        wait_for_status(
                        request, 
                        response, 
                        status = 'DONE', 
                        interval = 10)

    #@staticmethod
    def create_image(self, image_name, source_disk, force=False):
        """ Create a GCP instance image.

        Images API methods:
            https://cloud.google.com/compute/docs/reference/latest/images
        Python Compute API example:
            https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/compute/api/create_instance.py

        Status: Untested
        """

        config = {                  
                  "name": image_name,
                  "sourceDisk": source_disk 
                 }

        # Throw error if source_disk instance is still running
        ## gcloud api probably throws error anyway
        request_id = str(uuid.uuid4())
        request = compute.images().insert(
                                          project = project, 
                                          forceCreate = force,
                                          body = config,
                                          requestId = request_id)
        response = request.execute()
        wait_for_status(
                        request, 
                        response, 
                        status = 'DONE', 
                        interval = 10)

    #@staticmethod
    def delete_image(self, image_name, timeout=300):
        """ Delete a GCP instance image.

        Status: Untested.
        """

        request = compute.images().delete(
                                          project = project, 
                                          image = image_name)
        response = request.execute()
        self._wait_for_status(request, response, 'DONE', timeout)

def wait_for_status(request, response, status='DONE', timeout=300, interval=5):
    """ Wait for Google Cloud API request to complete.

    Possible status are PENDING, RUNNING, or DONE.

    Status: Untested.
    """

    timeout_cycles = int(timeout)/interval

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
        n += 1
        if n >= timeout_cycles:
            raise TimeoutError("Operation exceeded timeout period. " +
                               "{}: {}.".format(op_kind, op_type))
        sleep(interval)
        response = request.execute()
        op_kind = response['kind']
        op_type = response['operationType']
        op_status = response['status']
        pprint("Waiting for operation. {}: {}; {}.".format(
                                                          op_kind,
                                                          op_type,
                                                          op_status))
    pprint("Operation complete. {}: {}; {}.".format(
                                               op_kind,
                                               op_type,
                                               op_status))
    pprint("=================")


def parse_args(args):

    parser = argparse.ArgumentParser()
    parser.add_argument(
                        '--config', 
                        dest = 'config_file', 
                        type = str,
                        help = 'Yaml file with deployment settings.')
    parser.add_argument(
                        '--dry-run',
                        dest = 'dry_run',
                        default = False,
                        action = 'store_true',
                        help = 'Do not make system calls when running.')
    args = parser.parse_args(args)
    return args 

def main():

    if sys.version_info[0] < 3:
        raise "Must be using Python 3"

    # Create Google compute API service object
    compute = googleapiclient.discovery.build('compute', 'v1')

    deployments = {}

    # Parse command-line arguments
    args = parse_args(sys.argv[1:])
    config_file = args.config_file
    dry_run = args.dry_run

    with open(config_file) as config_fh:
        config = yaml.load(config_fh)
    deployment_sets = config['terraform_sets']

    # TODO: Update to handle different classes (i.e. GIMS)
    # Create deployment objects from config file
    
    for config in deployment_sets:
        deployment = get_deployment_object(config)

        #deployment = TerraformDeployment(
        #                                 name = config['name'],
        #                                 var_file = config['var-file'],
        #                                 state_file = config['state-file'])
        deployments[deployment.name] = deployment

    # Make system calls to run Terraform
    for deployment in deployments.values():
        #deployment.plan(dry_run)
        #deployment.destroy(dry_run)
        #deployment.apply(dry_run)
        deployment.run(dry_run)

if __name__ == "__main__":
    main()
