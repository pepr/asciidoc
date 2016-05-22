#!/usr/bin/env python

from __future__ import print_function
import mimetypes, base64, sys
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-n", "--no-uri", default=False, action="store_true")
parser.add_option("-s", "--src-prefix", default=False, action="store_true")

opts, args = parser.parse_args()

if opts.src_prefix:
	print("src=\x22", end='')

if not opts.no_uri:
	print('data:'+mimetypes.guess_type(args[-1])[0]+';base64,', end='')

with open(args[-1], 'rb') as f:
	# this is ok since we're always guaranteed text from base64.encode funcs
	if sys.version_info[0] == 3:
		print(base64.encodebytes(f.read()).decode('utf-8'), end='')
	else:
		base64.encode(f, sys.stdout)
