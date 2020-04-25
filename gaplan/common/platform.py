# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import sys
import os

from gaplan.common.error import error_if

def open_file(f):
  if sys.platform == 'cygwin':
    rc = os.system('cygstart %s' % f)
  elif sys.platform.startswith('win'):
    rc = os.system('explorer %s' % f)
  else:
    rc = os.system('xdg-open %s' % f)
  error_if(0 != rc, "failed to open pdf file '%s'" % f)
