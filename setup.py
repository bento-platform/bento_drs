#!/usr/bin/env python

import setuptools

with open("README.md", "r") as rf:
    long_description = rf.read()

setuptools.setup(
    name="chord_drs",
    version="0.1.0",

    python_requires=">=3.6",
    install_requires=[
        "chord_lib @ git+https://github.com/c3g/chord_lib",
        "Flask", 
        "SQLAlchemy", 
        "Flask-SQLAlchemy", 
        "Flask-Migrate"
    ],

    author="Simon Chénard",
    author_email="simon.chenard2@mcgill.ca",

    description="An implementation of a data repository system (as per GA4GH's specs) for the CHORD project.",
    long_description=long_description,
    long_description_content_type="text/markdown",

    packages=["chord_drs"],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'ingest=chord_drs.commands:ingest'
        ],
    },

    url="https://github.com/c3g/chord_drs",
    license="LGPLv3",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ]
)
