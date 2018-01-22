#!/usr/bin/env python

import mock
import yaml
import unittest

from sprout import parse_args
from sprout import TerraformDeployment

class TestTerraformDeployment(unittest.TestCase):

    @mock.patch('sprout.call')
    def test_basic_tf_plan_call(self, mock_call):
        name = 'development'
        var_file = 'test.tfvars'
        state_file = 'tfstate-files/test.tfstate'
        #variables = {'version': '0.1'}

        basic_plan_call = [
                           "terraform",
                           "plan",
                           "-var-file={}".format(var_file),
                           "-state={}".format(state_file)]

        deployment = TerraformDeployment(
                                         name = name,
                                         var_file = var_file, 
                                         state_file = state_file)
        deployment.plan()
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
            
class ParseArgsTestCase(unittest.TestCase):

    def test_config_arg(self):
        args = parse_args(['--config', 'sprout_unittest.yaml'])
        self.assertTrue(args.config_file == "sprout_unittest.yaml")


if __name__ == '__main__':
    unittest.main()


