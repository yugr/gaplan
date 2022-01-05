#!/bin/sh

# Copyright 2020-2021 Yury Gribov
#
# The MIT License (MIT)
# 
# Use of this source code is governed by MIT license that can be
# found in the LICENSE.txt file.

set -eu

if test -n "${TRAVIS:-}" -o -n "${GITHUB_ACTIONS:-}"; then
  set -x
fi

cd $(dirname $0)/..

PYTHON=${PYTHON:-python3}

$PYTHON -mpip install -e .

export PYTEST="${PYTEST:-$PYTHON -mpytest}"
$PYTEST gaplan
