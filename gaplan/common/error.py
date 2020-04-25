# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

from gaplan.common.location import Location

import sys
import os.path

_print_stack = False
_me = os.path.basename(sys.argv[0])

def error(*args):
  if isinstance(args[0], Location):
    loc, msg = args
    sys.stderr.write('%s: error: %s: %s\n' % (_me, loc, msg))
  else:
    msg, = args
    sys.stderr.write('%s: error: %s\n' % (_me, msg))
  if _print_stack:
    raise RuntimeError
  else:
    sys.exit(1)

def error_if(cond, *args):
  if cond:
    error(*args)

def warn(*args):
  if isinstance(args[0], Location):
    loc, msg = args
    sys.stderr.write('%s: warning: %s: %s\n' % (_me, loc, msg))
  else:
    msg, = args
    sys.stderr.write('%s: warning: %s\n' % (_me, msg))

def warn_if(cond, *args):
  if cond:
    warn(*args)

def set_basename(name):
  global _me
  _me = name

def set_options(**kwargs):
  for k, v in kwargs.items():
    if k == 'print_stack':
      global _print_stack
      _print_stack = v
    else:
      error("error: unknown option: " + k)
