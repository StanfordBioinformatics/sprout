#!/usr/bin/env python

import yaml

from subprocess import call

class TerraformDeployment:

    def __init__(self, var_file, state_file, variables):
        """Manage Terraform deployment process.


        """

        self.var_file = var_file
        self.state_file = state_file
        self.variables = variables

    def add_variables(self, variable_dict):
        for key, value in variable_dict.iteritems():
            self.variables.append("-var '{}={}'".format(key, value))

    def launch(self):
        command_list = [
                        "-var-file={}".format(self.var_file),
                        "-state={}".format(self.state_file),
                        variables]
        #command_list.append(variables)
        call(['terraform', 'destroy', command_list])
        call(['terraform', 'apply', command_list])


def main():

    deployments = []
    variables = {}

    parse_args()

    config = yaml.load(args.yaml_fileparse_yaml)
    terraform_sets = config['terraform_sets']
    for set in terraform_sets:
        deployment = TerraformDeployment(set)
        if cl_variables:
            deployment.add_variables(variables)
        deployments.append(deployment)

    # Create TerraformDeployment objects

    parse_cl_args()
    # Add additional TF variables passed on command line