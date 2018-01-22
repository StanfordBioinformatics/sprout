#!/usr/bin/env python3

import sys
import yaml
import argparse

from subprocess import call

class TerraformDeployment:

    def __init__(self, name, var_file, state_file, variables=None):
        """ Manage Terraform deployment process.


        """

        self.name = name
        self.var_file = var_file
        self.state_file = state_file
        self.variables = variables

    def add_variables(self, variable_dict):
        """ Add/overwrite Terraform variables.

        Hold off on developing this.
        """
        for key, value in variable_dict.iteritems():
            self.variables.append("-var '{}={}'".format(key, value))

    def launch(self, tf_command, dry_run):
        """ Launch Terraform deployment process.
        """
        arguments = ['terraform', tf_command]
        arguments.append("-var-file={}".format(self.var_file))
        arguments.append("-state={}".format(self.state_file))
        if dry_run:
            print(arguments)
        else:
            call(arguments)

    def destroy(self, dry_run):
        """ Call Terraform with 'destroy' command.
        """
        self.launch(tf_command='destroy', dry_run=dry_run)

    def plan(self, dry_run):
        """ Call Terraform with 'plan' command.
        """
        self.launch(tf_command='plan', dry_run=dry_run)

    def apply(self, dry_run):
        """ Call Terraform with 'apply' command.
        """
        self.launch(tf_command='apply', dry_run=dry_run)

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

    deployments = {}

    # Parse command-line arguments
    args = parse_args(sys.argv[1:])
    config_file = args.config_file
    dry_run = args.dry_run

    with open(config_file) as config_fh:
        config = yaml.load(config_fh)

    # Create deployment objects from config file
    terraform_sets = config['terraform_sets']
    for tf_set in terraform_sets:
        deployment = TerraformDeployment(
                                         name = tf_set['name'],
                                         var_file = tf_set['var-file'],
                                         state_file = tf_set['state-file'])
        deployments[deployment.name] = deployment

    # Make system calls to run Terraform
    for deployment in deployments.values():
        deployment.plan(dry_run)
        deployment.destroy(dry_run)
        deployment.apply(dry_run)

if __name__ == "__main__":
    main()
