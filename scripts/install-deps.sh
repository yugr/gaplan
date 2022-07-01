#!/bin/sh

# The MIT License (MIT)
# 
# Copyright (c) 2022 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

set -eu
set -x

PYTHON=${PYTHON:-python3}

sudo apt-get update
sudo apt-get -y install $PYTHON
sudo apt-get -y install $PYTHON-pip || true
# distutils is needed by pip
sudo apt-get -y install $PYTHON-distutils || true
sudo $PYTHON -m pip install setuptools pytest
