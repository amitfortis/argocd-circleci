#!/bin/bash
set -e

curl -s $1:5000 >/dev/null || exit 1
echo "Successfully connected!"
