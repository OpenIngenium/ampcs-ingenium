import os
from setuptools import setup, find_packages


# Used for the long_description to read in README file.
def read(file_name):
    return open(os.path.join(os.path.dirname(__file__), file_name)).read()


def get_version(file_name):
    version = {}
    with open(os.path.join(os.path.dirname(__file__), file_name)) as fp:
        exec(fp.read(), version)
    return version['__version__']


setup(
    name='ampcs_ing_lib',
    packages=find_packages(),
    install_requires=[    ],
    description="JPL specific libraries and functions for Ingenium",
    version=get_version(os.path.join('ing-lib-jpl', '__init__.py')),
    python_requires='>=3.9',
    entry_points={
        'console_scripts': []
    },
    author="Christopher Swan",
    author_email="open-ingenium@jpl.nasa.gov",
    url=""
)