# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""Platform abstraction APIs."""

import sys
import os

from gaplan.common.error import error_if

def open_file(filename):
  """Open file with appropriate reader."""
  if sys.platform == 'cygwin':
    rc = os.system('cygstart %s' % filename)
  elif sys.platform.startswith('win'):
    rc = os.system('explorer %s' % filename)
  else:
    rc = os.system('xdg-open %s' % filename)
  error_if(rc != 0, "failed to open pdf file '%s'" % filename)
