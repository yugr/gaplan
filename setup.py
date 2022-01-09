#!/usr/bin/python3

# The MIT License (MIT)
# 
# Copyright (c) 2018-2022 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import setuptools

with open('README.md', 'r') as f:
  long_description = f.read()

setuptools.setup(
  name='gaplan',
  version='0.1',
  author='Yury Gribov',
  author_email='tetra2005@gmail.com',
  description="Toolset for constructing and analyzing declarative plans",
  long_description=long_description,
  long_description_content_type='text/markdown',
  url='https://github.com/yugr/gaplan',
  packages=setuptools.find_packages(exclude=['test']),
  classifiers=[
    'Programming Language :: Python :: 3',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
  ],
)
