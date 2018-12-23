# The MIT License (MIT)
# 
# Copyright (c) 2016-2018 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import re

# "Regex cacher" which allows doing things like
#   if Re.match(...):
#     x = Re.group(1)

last_match = None

def match(*args, **kwargs):
  global last_match
  last_match = re.match(*args, **kwargs)
  return last_match

def search(*args, **kwargs):
  global last_match
  last_match = re.search(*args, **kwargs)
  return last_match

def fullmatch(*args, **kwargs):
  global last_match
  last_match = re.fullmatch(*args, **kwargs)
  return last_match

def group(*args, **kwargs):
  return last_match.group(*args, *kwargs)

def groups(*args, **kwargs):
  return last_match.groups(*args, **kwargs)
