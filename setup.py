#!/usr/bin/env python

from setuptools import setup


with open('README.md', 'r') as fh:
    long_description = fh.read()

setup(
    name='kirke',
    version='0.1',
    packages=['kirke'],
    url='https://github.com/xlfe/kirke',
    license='GNU General Public License v3.0',
    author='xlfe',
    description='circe is a state and transition abstraction manager for Python 3.5+',
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers = [
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ]
)
