# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4
# clamavmirror: ClamAV Signature Mirroring Tool
# Copyright (C) 2015 Andrew Colin Kissa <andrew@topdog.za.net>
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""
clamavmirror: ClamAV Signature Mirroring Tool

Copyright 2015, Andrew Colin Kissa
Licensed under MPL 2.0.
"""
import os

# from imp import load_source
from setuptools import setup


def get_readme():
    """Generate long description"""
    pandoc = None
    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        pandoc = os.path.join(path, 'pandoc')
        if os.path.isfile(pandoc) and os.access(pandoc, os.X_OK):
            break
    try:
        if pandoc:
            cmd = [pandoc, '-t', 'rst', 'README.md']
            long_description = os.popen(' '.join(cmd)).read()
        else:
            raise ValueError
    except BaseException:
        long_description = open("README.md").read()
    return long_description


# pylint: disable-msg=W0142
def main():
    """Main"""

    opts = dict(
        name="clamavmirror",
        version='0.0.2',
        description="ClamAV Signature Mirroring Tool",
        long_description=get_readme(),
        keywords="clamav mirror mirroring mirror-tool signatures",
        author="Andrew Colin Kissa",
        author_email="andrew@topdog.za.net",
        url="https://github.com/akissa/clamavmirror",
        license="MPL 2.0",
        packages=[],
        scripts=['bin/clamavmirror'],
        include_package_data=True,
        zip_safe=False,
        install_requires=['urlgrabber', 'dnspython'],
        classifiers=[
            'Development Status :: 4 - Beta',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Intended Audience :: System Administrators',
            'Environment :: Console',
            'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)',
            'Natural Language :: English',
            'Operating System :: OS Independent'],)
    setup(**opts)


if __name__ == "__main__":
    main()
