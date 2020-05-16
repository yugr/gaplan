# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""Error handling APIs."""

from gaplan.common.location import Location

import sys
import os.path

_print_stack = False
_me = os.path.basename(sys.argv[0])

def error(*args):
  """Prints pretty error message and terminates."""
  if isinstance(args[0], Location):
    loc, msg = args
    sys.stderr.write("%s: error: %s: %s\n" % (_me, loc, msg))
  else:
    msg, = args
    sys.stderr.write("%s: error: %s\n" % (_me, msg))
  if _print_stack:
    raise RuntimeError
  else:
    sys.exit(1)

def error_if(cond, *args):
  """Report error if condition is true."""
  if cond:
    error(*args)

def warn(*args):
  """Prints pretty warning message."""
  if isinstance(args[0], Location):
    loc, msg = args
    sys.stderr.write("%s: warning: %s: %s\n" % (_me, loc, msg))
  else:
    msg, = args
    sys.stderr.write("%s: warning: %s\n" % (_me, msg))

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
