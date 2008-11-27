#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project           :   Pamela
# -----------------------------------------------------------------------------
# Author            :   Sebastien Pierre                 <sebastien@type-z.org>
# License           :   Lesser GNU Public License
# -----------------------------------------------------------------------------
# Creation date     :   01-Jun-2007
# Last mod.         :   20-Nov-2008
# -----------------------------------------------------------------------------

import os, sys, re
import engine
import railways
from railways.contrib.localfiles import LocalFiles
from railways.contrib.cache import Cache

CACHE = Cache()

def processPamela( pamelaText, path ):
	parser = engine.Parser()
	result = parser.parseString(pamelaText)
	return result, "text/html"

def processSugar( sugarText, path ):
	timestamp         = CACHE.filemod(path)
	has_changed, data = CACHE.get(path,timestamp)
	if has_changed:
		try:
			from sugar import main as sugar
		except Exception, e:
			print "Sugar/LambdaFactory is not available"
			print e
			return sugarText, "text/plain"
		modulename = os.path.splitext(os.path.basename(path))[0]
		data = sugar.sourceToJavaScript(sugarText, modulename)
		CACHE.put(path,timestamp,data)
	return data, "text/plain"

def getProcessors():
	"""Returns a dictionary with the Railways LocalFiles processors already
	setup."""
	return {"paml":processPamela, "sjs":processSugar}

def getLocalFile():
	"""Returns a Railways LocalFile component initialized with the Pamela
	processor."""
	return LocalFiles(processors=getProcessors())

def run( arguments ):
	files  = getLocalFile()
	app    = railways.Application(components=(files,))
	railways.command(arguments, app=app,sessions=False)

# -----------------------------------------------------------------------------
#
# Main
#
# -----------------------------------------------------------------------------

if __name__ == "__main__":
	run(sys.argv[1:])

# EOF


