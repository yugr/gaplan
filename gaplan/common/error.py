# The MIT License (MIT)
# 
# Copyright (c) 2018-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""Error handling APIs."""

import sys
import os.path
from typing import NoReturn

from gaplan.common.location import Location

_print_stack = False
_me = os.path.basename(sys.argv[0])

def error(*args) -> NoReturn:
  """Prints pretty error message and terminates."""
  if isinstance(args[0], Location):
    loc, msg = args
    sys.stderr.write(f"{_me}: error: {loc}: {msg}\n")
  else:
    msg, = args
    sys.stderr.write(f"{_me}: error: {msg}\n")
  if _print_stack:
    raise RuntimeError
  sys.exit(1)

def error_if(cond, *args):
  """Report error if condition is true."""
  if cond:
    error(*args)

def warn(*args):
  """Prints pretty warning message."""
  if isinstance(args[0], Location):
    loc, msg = args
    sys.stderr.write(f"{_me}: warning: {loc}: {msg}\n")
  else:
    msg, = args
    sys.stderr.write(f"{_me}: warning: {msg}\n")

def warn_if(cond, *args):
  """Report warning if condition is true."""
  if cond:
    warn(*args)

def set_basename(name):
  """Set program name for error reports."""
  global _me
  _me = name

def set_options(**kwargs):
  """Set other error-reporting options."""
  for k, v in kwargs.items():
    if k == 'print_stack':
      global _print_stack
      _print_stack = v
    else:
      error("error: unknown option: " + k)
