#!/usr/bin/env python

import mock
import unittest

from sprout import TerraformDeployment

class TestTerraformDeployment(unittest.TestCase):

    @mock.patch('mymodule.subprocess')
    def test_launch(self):
        var_file = 'test.tfvars'
        state_file = 'test.tfstate'
        variables = {'version': '0.1'}

        true_delete_call = (
                            "terraform delete " +
                            "-var-file={} ".format(var_file) +
                            "-state=file={} ".format(state_file) +
                            "-var 'version=0.1'")

        deployment = TerraformDeployment(var_file, state_file, variables)
        mock_subprocess.call.assert_called_with(true_delete_call)

if __name__ == '__main__':
    unittest.main()


