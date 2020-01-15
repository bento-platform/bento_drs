#!/usr/bin/env python

import setuptools

with open("README.md", "r") as rf:
    long_description = rf.read()

setuptools.setup(
    name="chord_drs",
    version="0.1.0",

    python_requires=">=3.6",
    install_requires=[
        "chord_lib[flask]==0.1.0",
        "Flask>=1.1,<2.0",
        "SQLAlchemy>=1.3,<1.4",
        "Flask-SQLAlchemy>=2.4,<3.0",
        "Flask-Migrate>=2.5,<3.0"
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
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Operating System :: OS Independent"
    ]
)
