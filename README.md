# ClamAV Signature Mirroring Tool

## Why

The existing [clamdownloader.pl](https://github.com/akissa/clamav-faq/blob/master/mirrors/clamdownloader.pl)
script does not have any error correction it simply bails out if a downloaded
file is not valid and is unable to retry different mirrors if one fails.

This script will retry if a download fails with an http code that is not 404,
it will connect to another mirror if retries fail or file not found or if the
downloaded file is invalid.

It has options to set the locations for the working and mirror directory as
well as user/group ownership for the downloaded files. It uses locking to
prevent multiple instances from running at the same time.

## Requirements

* UrlGrabber module - http://urlgrabber.baseurl.org/
* DNS-Python module - http://www.dnspython.org/

## Usage

    $ clamavmirror -h

Usage: clamavmirror.py [options]

```bash
Options:
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
                        Lock files directory```

## Example Usage

    $ clamavmirror -w ~/tmp/clamavtmp/ \
    -d ~/tmp/clamavmirror/ -u andrew -g staff -a db.za.clamav.net \
    -l ~/Downloads/


## Installation

Install from PyPi

    pip install clamavmirror

Install from Githib

    git clone https://github.com/akissa/clamavmirror.git
    cd clamavmirror
    python setup.py install

## Contributing

1. Fork it (https://github.com/akissa/clamavmirror/fork)
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create new Pull Request


## License

All code is licensed under the
[MPLv2 License](https://github.com/akissa/clamavmirror/blob/master/LICENSE).
