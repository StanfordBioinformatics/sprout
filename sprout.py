#!/usr/bin/env python2

import os
import sys
import hcl
import pdb
import uuid
import yaml
import argparse
import subprocess

from time import sleep
from pprint import pprint

import googleapiclient.discovery
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

class BaseDeployment:

    def __init__(self, root, state_file, var_files):
        """ Manage Terraform deployment process.

            name(str): Arbitrary name of this deployment process
            state_file(str): Path to tfstate file
            var_files(list): List of tfvars files
        """
        self.root = root
        self.state_file = state_file
        self.var_files = var_files

    def _launch(self, tf_commands, dry_run, timeout=3600):
        """ Launch Terraform deployment process.

        args:
            tf_command (str): Terraform command to run
            dry_run (bool): If true will just print command
            timeout (int): Command timeout in seconds
        """
        arguments = ['terraform']
        for option in tf_commands:
            arguments.append(option)
        for var_file in self.var_files:
            arguments.append("-var-file={}".format(var_file))
        arguments.append("-state={}".format(self.state_file))

        print("Command: ", arguments, "cwd=", self.root)
        if dry_run:
            sys.exit(0)

        deploy_complete = False
        tries = 3
        while deploy_complete == False and tries > 0:
            try:
		home_dir = os.getcwd()
		os.chdir(self.root)
                subprocess.check_call(arguments)
		deploy_complete = True
		os.chdir(home_dir)
            except subprocess.CalledProcessError as err:
                # TODO: change subprocess fnc to check_call() or check_ouput()
                # TODO: add CalledProcessError handling
                tries -= 1
                print("WARNING: deployment operations failed to complete ",
                      "within timeout period. ")
                print("Command: ", err.cmd)
                print("Output: ", err.output)
                print("Tries remaining: ", tries)
                os.chdir(home_dir)

    def destroy(self, dry_run, timeout):
        """ Call Terraform with 'destroy' command.
        """
        self._launch(
                    tf_commands = ['destroy', '-force'],
                    dry_run = dry_run,
                    timeout = timeout)

    def plan(self, dry_run, timeout):
        """ Call Terraform with 'plan' command.
        """
        self._launch(
                     tf_commands = ['plan'],
                     dry_run = dry_run,
                     timeout = timeout)

    def apply(self, dry_run, timeout):
        """ Call Terraform with 'apply' command.
        """
        self._launch(
                     tf_commands = ['apply', '-auto-approve'],
                     dry_run = dry_run,
                     timeout = timeout)

    def full_run(self, dry_run):
        """ Run full deployment pipeline.

        Run destroy and apply.
        """
        self.destroy(dry_run)
        self.plan(dry_run)
        self.apply(dry_run)


class BalancerDeployment(BaseDeployment, object):

    def __init__(self, root, state_file, var_files):
        super(BalancerDeployment, self).__init__(root, state_file, var_files)
        
        self.vars = {}

        # Read data from tfvars files into dictionary
        for var_file in self.var_files:
            with open(var_file, 'r') as fh:
                new_vars = hcl.load(fh)
                self.vars.update(new_vars)

        self.project = self.vars['project']
        self.zone = self.vars['zone']
        self.instance_name = self.vars['instance_name']
        self.image_name = self.vars['template_image']
        self.instance_group = self.vars['instance_group']

        self.source_disk = "zones/{}/disks/{}".format(
                                                      self.zone,
                                                      self.instance_name)
        
        # Get service key path and create Google API client
        service_key_name = self.vars['service_account_key']
	self.service_key = os.path.join(root, service_key_name)
        self.compute = ComputeOperator(self.service_key)	

    def full_run(self, dry_run):
        """ Run full deployment pipeline.
        """

        self.destroy(dry_run)
        self.apply(dry_run)
        if not dry_run:
            self.load_to_balancer(dry_run)

    def load_to_balancer(self,  dry_run):
        """Deploy instance to load balancer.

        Does not run new Terraform deployment.
        """
        if dry_run:
            sys.exit(0)

        self.compute.stop_instance(
                              name = self.instance_name,
                              project = self.project,
                              zone = self.zone)
        self.compute.delete_image(
                             image_name = self.image_name,
                             project = self.project)
        self.compute.create_image(
                             image_name = self.image_name,
                             source_disk = self.source_disk,
                             project = self.project)
        group_instances = self.compute.list_group_instances(
                                                       group_name = self.instance_group,
                                                       project = self.project,
                                                       zone = self.zone)
        for instance_dict in group_instances:
            instance = instance_dict['instance']
            instance_name = instance.split('/')[-1]
            self.compute.delete_instance(
                                    name = instance_name,
                                    project = self.project,
                                    zone = self.zone)


class ComputeOperator:

    def __init__(self, account_key_json):
        """ 

        Status: Untested.
        """
        
        #self.credentials = GoogleCredentials.get_application_default()
        self.credentials = service_account.Credentials.from_service_account_file(
									account_key_json)
        self.client = googleapiclient.discovery.build(
                                                      'compute',
                                                      'v1',
                                                      credentials = self.credentials)

    def stop_instance(self, name, project, zone):
        """ Stop a running GCP instance.

        Status: Tested.
        """
        request_id = str(uuid.uuid4())
        request = self.client.instances().stop(
                                                project = project,
                                                zone = zone,
                                                instance = name,
                                                requestId = request_id)
        response = request.execute()
        wait_for_status(
                        request, 
                        response, 
                        status = 'DONE', 
                        interval = 10)

    def delete_instance(self, name, project, zone):
        """ Delete a GCP compute instance.

        Status: Untested.
        """
        print("Deleting instance: {}".format(name))
        request_id = str(uuid.uuid4())
        request = self.client.instances().delete(
                                                  project = project,
                                                  zone = zone,
                                                  instance = name,
                                                  requestId = request_id)
        try:
            response = request.execute()
            wait_for_status(
                            request,
                            response,
                            status = 'DONE',
                            interval = 10)
        except HttpError as err:
            if err.resp.status in [404]:
                pprint("INFO: Skipping delete; instance does not exist.")
                pass
            else:
                raise

    def list_group_instances(self, group_name, project, zone):
        """Get a list of instances running in instance group

        args:
            group_name (str): Name of instance group

        returns:
            list of dicts with instance metadata
        """

        request_body = {"instanceState": "RUNNING"}
        request = self.client.instanceGroups().listInstances(
                                                project = project,
                                                zone = zone,
                                                instanceGroup = group_name,
                                                body = request_body)
        response = request.execute()
        return response['items']

    def create_image(self, image_name, source_disk, project, force=False):
        """ Create a GCP instance image.

        Images API methods:
            https://cloud.google.com/compute/docs/reference/latest/images
        Python Compute API example:
            https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/compute/api/create_instance.py

        Status: Untested
        """
        pprint("Creating image \"{}\" from source disk \"{}\".".format(image_name, source_disk))
        config = {                  
                  "name": image_name,
                  "sourceDisk": source_disk 
                 }

        # Throw error if source_disk instance is still running
        ## gcloud api probably throws error anyway
        request_id = str(uuid.uuid4())
        request = self.client.images().insert(
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

    def delete_image(self, image_name, project, timeout=300):
        """ Delete a GCP instance image.

        Status: Untested.
        """
        pprint("Deleting image: {}".format(image_name))
        request = self.client.images().delete(
                                              project = project,
                                              image = image_name)
        try:
            response = request.execute()
            wait_for_status(request, response, 'DONE', timeout)
        except HttpError as err:
            if err.resp.status in [404]:
                pprint("INFO: Skipping delete; image does not exist.")
                pass
            else:
                raise

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

def get_deployment_object(config):

    root = config['root']
    state_file = os.path.join(root, config['state-file'])

    var_files = []
    for var_file in config['var-files']:
        var_path = os.path.join(root, var_file)
        var_files.append(var_path)
    # Same operation using a map function (less readable)
    # var_files = list(map(lambda var_file: os.path.join(config['root'], var_file), config['var-files']))

    if config['load-balancer']:
        deployment = BalancerDeployment(root, state_file, var_files)
    else:
        deployment = BaseDeployment(root, state_file, var_files)
    return deployment

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

    if len(args) < 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args(args)
    return args 

def main():

    ## Deployment node uses Python 2 :/
    #if sys.version_info[0] < 3:
    #    raise "Must be using Python 3"

    ## Invidual API clients now created per deployment
    # Create Google compute API service object
    #compute = googleapiclient.discovery.build('compute', 'v1')
    #compute = ComputeOperator()

    # Parse command-line arguments
    args = parse_args(sys.argv[1:])
    config_file = args.config_file
    dry_run = args.dry_run

    with open(config_file) as config_fh:
        config = yaml.load(config_fh)
    deployment_sets = config['terraform_sets']

    # Create deployment objects from config file
    deployments = []
    for config in deployment_sets:
        # Config object is a dictionary with deployment info
        #print(config, "\n")
        deployment = get_deployment_object(config)
        deployments.append(deployment)
    #print(deployments)

    # Make system calls to run Terraform
    for deployment in deployments:
        print(deployment)
        if isinstance(deployment, BalancerDeployment):
            print("Launching load balancer deployment")
            deployment.plan(dry_run, timeout=60)
            deployment.destroy(dry_run, timeout=300)
            deployment.apply(dry_run, timeout=1200)
            deployment.load_to_balancer(dry_run)
        elif isinstance(deployment, BaseDeployment):
            print("Launching base deployment")
            deployment.plan(dry_run, timeout=60)
            deployment.destroy(dry_run, timeout=300)
            deployment.apply(dry_run, timeout=1200)

if __name__ == "__main__":
    main()
