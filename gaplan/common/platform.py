# The MIT License (MIT)
# 
# Copyright (c) 2018-2022 Yury Gribov
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
    rc = os.system(f'cygstart {filename}')
  elif sys.platform.startswith('win'):
    rc = os.system(f'explorer {filename}')
  else:
    rc = os.system(f'xdg-open {filename}')
  error_if(rc != 0, f"failed to open pdf file '{filename}'")
