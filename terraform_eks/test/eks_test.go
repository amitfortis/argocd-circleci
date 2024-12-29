package test

import (
        "testing"
        "github.com/gruntwork-io/terratest/modules/terraform"
        "github.com/stretchr/testify/assert"
)

func TestEKSCluster(t *testing.T) {
        t.Parallel()

        // Define Terraform options
        terraformOptions := &terraform.Options{
                // Path to the Terraform code
                TerraformDir: "../", // Assuming the test folder is inside the terraform folder
        }

        // Run Terraform init to initialize the working directory and download necessary providers
        terraform.Init(t, terraformOptions)
        terraform.Validate(t, terraformOptions)
        // Run Terraform plan and capture the output
        planOutput := terraform.Plan(t, terraformOptions)
        assert.Contains(t, planOutput, "eks_cluster", "The plan should contain an EKS cluster resource")

        assert.Contains(t, planOutput, "cluster_name", "The plan should contain the cluster_name output")
        assert.Contains(t, planOutput, "cluster_endpoint", "The plan should contain the cluster_endpoint output")
        assert.Contains(t, planOutput, "Plan:", "The plan should not propose destroying resources unless intended")

}
