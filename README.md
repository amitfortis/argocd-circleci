# Weather Application CI/CD Pipeline

A complete CI/CD pipeline project deploying a weather application to Amazon EKS using CircleCI, ArgoCD, and Infrastructure as Code.

## Project Structure

```
├── docker/                  # Docker configuration
├── myapp/                   # Helm chart for application
├── scripts/                 # Utility scripts
├── terraform_eks/          # EKS infrastructure code
└── web-project/           # Weather application source
```

## Components

### Infrastructure (terraform_eks/)
- EKS cluster configuration
- VPC module with networking setup
- Terraform test suite in Go
- Automated infrastructure provisioning

### Application (web-project/)
- Python-based weather application
- HTML templates and CSS styling
- Error handling pages
- Weather data processing

### Deployment (myapp/)
- Helm chart for Kubernetes deployment
- Configurable values
- Horizontal Pod Autoscaling
- Ingress configuration
- Persistent storage setup

### CI/CD
- CircleCI pipeline configuration
- ArgoCD GitOps deployment
- Docker container builds
- Automated testing and deployment


## Scripts

- `connection_test.sh`: Smoke connectivity test
- `delete_cluster.sh`: Clean up cluster
- `rebuild.sh`: Rebuild application and containers

## Requirements

- AWS CLI configured
- kubectl
- Terraform >= 1.0
- Helm >= 3.0
- Docker
- CircleCI CLI (optional)
- ArgoCD CLI (optional)



