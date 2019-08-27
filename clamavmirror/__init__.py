#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4
# clamavmirror: ClamAV Signature Mirroring Tool
# Copyright (C) 2015-2019 Andrew Colin Kissa <andrew@topdog.za.net>
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""ClamAV Signature Mirroring Tool

Why
---

The existing clamdownloader.pl script does not have any error
correction it simply bails out if a downloaded file is not
valid and is unable to retry different mirrors if one fails.

This script will retry if a download fails with an http code
that is not 404, it will connect to another mirror if retries
fail or file not found or if the downloaded file is invalid.

It has options to set the locations for the working and
mirror directory as well as user/group ownership for the
downloaded files. It uses locking to prevent multiple
instances from running at the same time.

Requirements
------------

Urllib3 module - https://urllib3.readthedocs.org
DNS-Python module - http://www.dnspython.org/

Usage
-----

$ clamavmirror -h
Usage: clamavmirror [options]

options:
  -h, --help            show this help message and exit
  -a HOSTNAME, --hostname=HOSTNAME
                        ClamAV source server hostname
  -r TXTRECORD, --text-record=TXTRECORD
                        ClamAV Updates TXT record
  -w WORKDIR, --work-directory=WORKDIR
                        Working directory
  -d MIRRORDIR, --mirror-directory=MIRRORDIR
                        The mirror directory
  -u USER, --user=USER  Change file owner to this user
  -g GROUP, --group=GROUP
                        Change file group to this group
  -l LOCKDIR, --locks-directory=LOCKDIR
                        Lock files directory

Example Usage
-------------

clamavmirror -w ~/tmp/clamavtmp/ -d ~/tmp/clamavmirror/ \
    -u andrew -g staff -a db.za.clamav.net \
    -l ~/Downloads/
"""
from __future__ import print_function
import os
import pwd
import grp
import sys
import time
import fcntl
import hashlib

from shutil import move

# Queue is called queue in python3
if sys.version_info.major < 3:
    from Queue import Queue
else:
    from queue import Queue

from threading import Thread
from optparse import OptionParser
from subprocess import PIPE, Popen

import certifi

from urllib3 import PoolManager, Timeout
from urllib3.util.request import make_headers
from dns.resolver import query, NXDOMAIN


VERSION_INFO = (0, 0, 4)
__author__ = "Andrew Colin Kissa"
__copyright__ = "© 2016-2019 Andrew Colin Kissa"
__email__ = "andrew@topdog.za.net"
__version__ = ".".join(map(str, VERSION_INFO))


def get_file_md5(filename):
    """Get a file's MD5"""
    if os.path.exists(filename):
        blocksize = 65536
        try:
            hasher = hashlib.md5()
        except BaseException:
            hasher = hashlib.new('md5', usedForSecurity=False)
        with open(filename, 'rb') as afile:
            buf = afile.read(blocksize)
            while len(buf) > 0:  # pylint: disable=len-as-condition
                hasher.update(buf)
                buf = afile.read(blocksize)
        return hasher.hexdigest()

    return ''


def get_md5(string):
    """Get a string's MD5"""
    try:
        hasher = hashlib.md5()
    except BaseException:
        hasher = hashlib.new('md5', usedForSecurity=False)
    hasher.update(string.encode('utf-8'))
    return hasher.hexdigest()


def error(msg):
    """print to stderr"""
    print(msg, file=sys.stderr)


def info(msg):
    """print to stdout"""
    print(msg, file=sys.stdout)


def deploy_signature(source, dest, user=None, group=None):
    """Deploy a signature fole"""
    move(source, dest)
    os.chmod(dest, 0o644)
    if user and group:
        try:
            uid = pwd.getpwnam(user).pw_uid
            gid = grp.getgrnam(group).gr_gid
            os.chown(dest, uid, gid)
        except (KeyError, OSError):
            pass


def create_file(name, content):
    "Generic to write file"
    with open(name, 'w') as writefile:
        writefile.write(content)


def get_txt_record(hostname):
    """Get the text record"""
    try:
        answers = query(hostname, 'TXT')
        return answers[0].strings[0].decode()
    except (IndexError, NXDOMAIN):
        return ''


def get_local_version(sigdir, sig):
    """Get the local version of a signature"""
    version = None
    filename = os.path.join(sigdir, '%s.cvd' % sig)
    if os.path.exists(filename):
        cmd = ['sigtool', '-i', filename]
        sigtool = Popen(cmd, stdout=PIPE, stderr=PIPE)
        while True:
            line = sigtool.stdout.readline().decode()
            if line and line.startswith('Version:'):
                version = line.split()[1]
                break
            if not line:
                break
        sigtool.wait()
    return version


def verify_sigfile(sigdir, sig):
    """Verify a signature file"""
    cmd = ['sigtool', '-i', '%s/%s.cvd' % (sigdir, sig)]
    sigtool = Popen(cmd, stdout=PIPE, stderr=PIPE)
    ret_val = sigtool.wait()
    return ret_val == 0


# pylint: disable=unused-argument
def check_download(obj, *args, **kwargs):
    """Verify a download"""
    version = args[0]
    workdir = args[1]
    signame = args[2]
    if version:
        local_version = get_local_version(workdir, signame)
        if not verify_sigfile(workdir, signame) or version != local_version:
            error("[-] \033[91mFailed to verify signature: %s from: %s\033[0m"
                  % (signame, obj.url))
            raise ValueError('Failed to verify signature: %s' % signame)


def download_sig(opts, sig, version=None):
    """Download signature from hostname"""
    code = None
    downloaded = False
    useagent = 'ClamAV/0.101.1 (OS: linux-gnu, ARCH: x86_64, CPU: x86_64)'
    manager = PoolManager(
        headers=make_headers(user_agent=useagent),
        cert_reqs='CERT_REQUIRED',
        ca_certs=certifi.where(),
        timeout=Timeout(connect=10.0, read=60.0)
    )
    if version:
        path = '/%s.cvd' % sig
        filename = os.path.join(opts.workdir, '%s.cvd' % sig)
    else:
        path = '/%s.cdiff' % sig
        filename = os.path.join(opts.workdir, '%s.cdiff' % sig)
    try:
        req = manager.request('GET', 'http://%s%s' % (opts.hostname, path))
    except BaseException as msg:
        error("Request error: %s" % msg)
    data = req.data
    code = req.status
    if req.status == 200:
        with open(filename, 'wb') as handle:
            handle.write(data)
        downloaded = os.path.exists(filename)
    return downloaded, code


def get_record(opts):
    """Get record"""
    count = 1
    for passno in range(1, 5):
        count = passno
        info("[+] \033[92mQuerying TXT record:\033[0m %s pass: %s" %
             (opts.txtrecord, passno))
        record = get_txt_record(opts.txtrecord)
        if record:
            info("=> Query returned: %s" % record)
            break
        else:
            info("=> Txt record query failed, sleeping 5 secs")
            time.sleep(5)
    if not record:
        error("=> Txt record query failed after %d tries" % count)
        sys.exit(3)
    return record


def copy_sig(sig, opts, isdiff):
    """Deploy a sig"""
    info("[+] \033[92mDeploying signature:\033[0m %s" % sig)
    if isdiff:
        sourcefile = os.path.join(opts.workdir, '%s.cdiff' % sig)
        destfile = os.path.join(opts.mirrordir, '%s.cdiff' % sig)
    else:
        sourcefile = os.path.join(opts.workdir, '%s.cvd' % sig)
        destfile = os.path.join(opts.mirrordir, '%s.cvd' % sig)
    deploy_signature(sourcefile, destfile, opts.user, opts.group)
    info("=> Deployed signature: %s" % sig)


def update_sig(queue):
    """update signature"""
    while True:
        options, sign, vers = queue.get()
        info("[+] \033[92mChecking signature version:\033[0m %s" % sign)
        localver = get_local_version(options.mirrordir, sign)
        remotever = vers[sign]
        if localver is None or (localver and int(localver) < int(remotever)):
            info("=> Update required local: %s => remote: %s" %
                 (localver, remotever))
            info("=> Downloading signature: %s" % sign)
            status, code = download_sig(options, sign, remotever)
            if status:
                info("=> Downloaded signature: %s" % sign)
                copy_sig(sign, options, 0)
            else:
                if code == 404:
                    error("=> \033[91mSignature:\033[0m %s not found" % sign)
                error("=> \033[91mDownload failed:\033[0m %s code: %d"
                      % (sign, code))
        else:
            info(
                "=> No update required L: %s => R: %s" % (localver, remotever))
        queue.task_done()


def update_diff(opts, sig):
    """Update diff"""
    for _ in range(1, 6):
        info("[+] \033[92mDownloading cdiff:\033[0m %s" % sig)
        status, code = download_sig(opts, sig)
        if status:
            info("=> Downloaded cdiff: %s" % sig)
            copy_sig(sig, opts, 1)
        else:
            if code == 404:
                error("=> \033[91mSignature:\033[0m %s not found" % sig)
            error("=> \033[91mDownload failed:\033[0m %s code: %d"
                  % (sig, code))


def create_dns_file(opts, record):
    """Create the DNS record file"""
    info("[+] \033[92mUpdating dns.txt file\033[0m")
    filename = os.path.join(opts.mirrordir, 'dns.txt')
    localmd5 = get_file_md5(filename)
    remotemd5 = get_md5(record)
    if localmd5 != remotemd5:
        create_file(filename, record)
        info("=> dns.txt file updated")
    else:
        info("=> No update required L: %s => R: %s" % (localmd5, remotemd5))


def download_diffs(queue):
    """Download the cdiff files"""
    while True:
        options, signature_type, localver, remotever = queue.get()
        for num in range(int(localver), int(remotever) + 1):
            sig_diff = '%s-%d' % (signature_type, num)
            filename = os.path.join(options.mirrordir, '%s.cdiff' % sig_diff)
            if not os.path.exists(filename):
                update_diff(options, sig_diff)
        queue.task_done()


def work(options):
    """The work functions"""
    # pylint: disable=too-many-locals
    record = get_record(options)
    _, mainv, dailyv, _, _, _, safebrowsingv, bytecodev = record.split(':')
    versions = {'main': mainv, 'daily': dailyv,
                'safebrowsing': safebrowsingv,
                'bytecode': bytecodev}
    dqueue = Queue(maxsize=0)
    dqueue_workers = 3
    info("[+] \033[92mStarting workers\033[0m")
    for index in range(dqueue_workers):
        info("=> Starting diff download worker: %d" % (index + 1))
        worker = Thread(target=download_diffs, args=(dqueue,))
        worker.setDaemon(True)
        worker.start()
    mqueue = Queue(maxsize=0)
    mqueue_workers = 4
    for index in range(mqueue_workers):
        info("=> Starting signature download worker: %d" % (index + 1))
        worker = Thread(target=update_sig, args=(mqueue,))
        worker.setDaemon(True)
        worker.start()
    for signature_type in ['main', 'daily', 'bytecode', 'safebrowsing']:
        if signature_type in ['daily', 'bytecode', 'safebrowsing']:
            # cdiff downloads
            localver = get_local_version(options.mirrordir, signature_type)
            remotever = versions[signature_type]
            if localver is not None:
                dqueue.put(
                    (
                        options,
                        signature_type,
                        localver,
                        remotever
                    )
                )
        mqueue.put((options, signature_type, versions))
    info("=> Waiting on workers to complete tasks")
    dqueue.join()
    mqueue.join()
    info("=> Workers done processing queues")
    create_dns_file(options, record)
    sys.exit(0)


def main():
    """Main entry point"""
    parser = OptionParser()
    parser.add_option('-a', '--hostname',
                      help='ClamAV source server hostname',
                      dest='hostname',
                      type='str',
                      default='db.de.clamav.net')
    parser.add_option('-r', '--text-record',
                      help='ClamAV Updates TXT record',
                      dest='txtrecord',
                      type='str',
                      default='current.cvd.clamav.net')
    parser.add_option('-w', '--work-directory',
                      help='Working directory',
                      dest='workdir',
                      type='str',
                      default='/var/spool/clamav-mirror')
    parser.add_option('-d', '--mirror-directory',
                      help='The mirror directory',
                      dest='mirrordir',
                      type='str',
                      default='/srv/www/clamav')
    parser.add_option('-u', '--user',
                      help='Change file owner to this user',
                      dest='user',
                      type='str',
                      default='nginx')
    parser.add_option('-g', '--group',
                      help='Change file group to this group',
                      dest='group',
                      type='str',
                      default='nginx')
    parser.add_option('-l', '--locks-directory',
                      help='Lock files directory',
                      dest='lockdir',
                      type='str',
                      default='/var/lock/subsys')
    parser.add_option('-v', '--verbose',
                      help='Display verbose output',
                      dest='verbose',
                      action='store_true',
                      default=False)
    options, _ = parser.parse_args()
    try:
        lockfile = os.path.join(options.lockdir, 'clamavmirror')
        with open(lockfile, 'w+') as lock:
            fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            work(options)
    except IOError:
        info("=> Another instance is already running")
        sys.exit(254)


if __name__ == '__main__':
    main()
