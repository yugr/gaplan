#!/bin/sh

# Copyright 2020 Yury Gribov
#
# The MIT License (MIT)
# 
# Use of this source code is governed by MIT license that can be
# found in the LICENSE.txt file.

set -eu

if test -n "${TRAVIS:-}"; then
  set -x
fi

cd $(dirname $0)/..

python3 -mpip install -e .

export PYTEST="${PYTEST:-python3 -mpytest}"
$PYTEST gaplan
