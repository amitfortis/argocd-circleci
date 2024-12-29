#!/bin/bash
docker stop $(docker ps -a -q)
tar --exclude '*/__pycache__' -czvf docker/web-project.tar.gz web-project/
cd ~/argocd+circleci/weather-application/docker/
docker build --no-cache -t registry.gitlab.com/amitfortis/weather-app:1.92 .
