# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup

with open("README.md") as f:
    readme = f.read()

setup(
    name="pydobiss",
    version="0.1.37",
    description="python interface to the dobiss developer api",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Kester Aernoudt",
    author_email="kesteraernoudt@yahoo.com",
    url="https://github.com/kesteraernoudt/pydobiss",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "pyjwt",
        "aiohttp",
    ],
)
