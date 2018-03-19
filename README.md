# sprout

## Design Notes

### Philosophy
* Purpose is to build a tool that will allow multiple Terraform deployments to be initiated with a single command
* Currently run into network issues when trying to do concurrent deployments, so tool should have option for sequential v concurrent
* One issue is that there are recurrent patterns within variable values that I will want to change
** i.e. branch version number; can I manage these?
* I want to try writing unit tests concurrently as I am writing functions, or conceptualize how they should work

### How does it work?
* Input: Terraform configuration file(s) (*.tf)
* Input: Terraform variable file(s) (*.tfvars)
* Input: Meta deployment configuration file (*.yaml)
* For each Terraform deployment:
** Create TerraformDeployment object
* Launch each deployment sequentially
** This should create "destroy" and "apply" system calls

### Roadmap
* Create virtualenv: Done
* Implement method to launch single deployment using default settings: Done
* Implement GimsDeployment child class of TerraformDeployment: In-progress
  * Create ComputeOperations class to organize instance operations: In-progress
    * Add functions to manage compute instances (i.e stop/delete/create instance): Done
    * Write unit tests for compute operations: In-progress
* Write tests for GimsDeployment
* Implement method to launch multiple deployments using default settings: Done
* Evaluate whether it is worthwhile to add variable functionality: No
* Add load-balancer functionality
