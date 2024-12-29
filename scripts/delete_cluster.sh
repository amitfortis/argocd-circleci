#!/bin/bash

kubectl delete all --all -n ingress-nginx
kubectl delete all --all -n argocd
kubectl delete all --all -n default
cd ../terraform_eks/
terraform destroy -auto-approve
