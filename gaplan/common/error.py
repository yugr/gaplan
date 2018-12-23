# The MIT License (MIT)
# 
# Copyright (c) 2016-2018 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import sys
import os.path

_print_stack = False
_me = os.path.basename(sys.argv[0])

def error(msg):
  sys.stderr.write('%s: error: %s\n' % (_me, msg))
  if _print_stack:
    raise StandardError
  else:
    sys.exit(1)

def error_loc(loc, msg):
  error('%s: %s' % (loc, msg))

def warn(msg):
  sys.stderr.write('%s: warning: %s\n' % (_me, msg))

def warn_loc(loc, msg):
  warn('%s: %s' % (loc, msg))

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
