# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

setup(
    name='pydobiss',
    version='0.1.12',
    description='python interface to the dobiss developer api',
    long_description=readme,
    long_description_content_type='text/markdown',
    author='Kester Aernoudt',
    author_email='kesteraernoudt@yahoo.com',
    url='https://github.com/kesteraernoudt/pydobiss',
    license='MIT',
    packages=find_packages(),
	install_requires=['asyncio',
                      'pyjwt',
                      'aiohttp',
                      ],
)

