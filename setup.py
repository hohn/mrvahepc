from setuptools import setup, find_packages
import glob

setup(
    name='mrvahepc',
    version='0.1.0',
    description='A Python package for serving CodeQL databases',
    author='Michael Hohn',
    author_email='hohn@github.com',
    packages=['mrvahepc'],
    install_requires=[],
    scripts=glob.glob("bin/mc-*"),
)
