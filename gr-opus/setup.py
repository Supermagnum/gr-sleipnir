#!/usr/bin/env python3
"""
Setup file for gr-opus GNU Radio OOT module
"""

from setuptools import setup, find_packages
import os

setup(
    name='gr-opus',
    version='1.0.0',
    description='GNU Radio Out-of-Tree module for Opus audio codec',
    author='gr-opus developers',
    url='https://github.com/yourusername/gr-opus',
    license='GPLv3',
    packages=find_packages(),
    install_requires=[
        'numpy',
        'opuslib',
    ],
    python_requires='>=3.6',
)

