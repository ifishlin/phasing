# Copyright (c) Twisted Matrix Laboratories.
#
# Copied from Twisted (http://twistedmatrix.com/), see
# http://twistedmatrix.com/trac/browser/trunk/LICENSE for the license.
#
# This makes sure that users don't have to set up their environment
# specially in order to run these programs from bin/.

# This helper can be shared by many different actual scripts.  It is not intended to
# be packaged or installed, it is only a developer convenience.  By the time
# the package is actually installed somewhere, the environment should already be set
# up properly without the help of this tool.

import sys, os

path = os.path.abspath(sys.argv[0])
while os.path.dirname(path) != path:
    if os.path.exists(os.path.join(path, 'HAHap', '__init__.py')):
        sys.path.insert(0, path)
        break
    path = os.path.dirname(path)

