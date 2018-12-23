# The MIT License (MIT)
# 
# Copyright (c) 2016-2018 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import sys
import os

from gaplan.common.error import error, warn

def open_file(f):
  if sys.platform == 'cygwin':
    rc = os.system('cygstart %s' % f)
  elif sys.platform.startswith('win'):
    rc = os.system('explorer %s' % f)
  else:
    rc = os.system('xdg-open %s' % f)
  if 0 != rc:
    error("failed to open pdf file '%s'" % f)
