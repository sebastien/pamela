#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project           :   Pamela
# -----------------------------------------------------------------------------
# Author            :   Sebastien Pierre           <sebastien.pierre@gmail.com>
# License           :   Lesser GNU Public License
# -----------------------------------------------------------------------------
# Creation date     :   2007-06-01
# Last mod.         :   2015-10-30
# -----------------------------------------------------------------------------

import os, sys, re, subprocess, tempfile, hashlib
from   pamela import engine
import retro
from   retro.contrib.localfiles import LocalFiles
from   retro.contrib.cache      import SignatureCache, MemoryCache
from   retro.contrib            import proxy

CACHE         = SignatureCache ()
MEMORY_CACHE  = MemoryCache ()
PROCESSORS    = {}
COMMANDS      = None
NOBRACKETS    = None
PANDOC_HEADER = """
<!DOCTYPE html>
<html><head>
<meta charset="utf-8" />
<link rel="stylesheet" href="http://ffctn.com/doc/css/base.css" />
<link rel="stylesheet" href="http://ffctn.com/doc/css/typography.css" />
<link rel="stylesheet" href="http://ffctn.com/doc/css/texto.css" />
</head><body class='use-base use-texto'><div class='document'>
"""
PANDOC_FOOTER = "</div></body></html>"

def getCommands():
	global COMMANDS
	if not COMMANDS:
		COMMANDS = dict(
			sugar       = os.environ.get("SUGAR",       "sugar"),
			coffee      = os.environ.get("COFFEE",      "coffee"),
			pythoniccss = os.environ.get("PYTHONICCSS", "pythoniccss"),
			pandoc      = os.environ.get("PANDOC",      "pandoc"),
			typescript  = os.environ.get("TYPESCRIPT",  "tsc"),
			babel       = os.environ.get("BABEL",       "babel"),
		)
	return COMMANDS

try:
	import templating
	HAS_TEMPLATING = templating
except:
	HAS_TEMPLATING = None

def processPamela( pamelaText, path, request=None ):
	parser = engine.Parser()
	if request and request.get("as") == "js":
		parser._formatter = engine.JSHTMLFormatter()
		result = parser.parseString(pamelaText, path)
		assign = request.get("assign")
		prefix = ""
		suffix = ""
		if assign:
			if assign == "_": assign = os.path.basename(path).split(".")[0]
			assign = assign.split(".")
			prefix = "var "
			suffix = ";"
			for i,v in enumerate(assign):
				if   i == 0:
					prefix += v + "=("
					suffix  = ")"    + suffix
				else:
					prefix += "{" + v + ":"
					suffix = "}" + suffix
		return prefix + result + suffix, "text/javascript"
	else:
		result = parser.parseString(pamelaText, path)
		return result, "text/html"

def processCleverCSS( text, path, request=None ):
	import clevercss
	result = clevercss.convert(text)
	return result, "text/css"

def cacheGet( text, path, cache ):
	if cache:
		if path:
			timestamp     = SignatureCache.mtime(path)
			is_same, data = CACHE.get(path,timestamp)
			cache = CACHE
			return cache, is_same, data, timestamp
		else:
			text    = engine.ensure_unicode(text)
			sig     = hashlib.sha256(bytes(u" ".join(command) + text)).hexdigest()
			cache   = MEMORY_CACHE
			is_same = cache.has(sig)
			data    = cache.get(sig)
			return cache, is_same, data, sig
	else:
		return cache, False, None, None

def _processCommand( command, text, path, cache=True, tmpsuffix="tmp", tmpprefix="pamela_", resolveData=None, allowEmpty=False):
	timestamp = has_changed = data = None
	cache, is_same, data, cache_key = cacheGet( text, path, cache)
	if (not is_same) or (not cache):
		if not path or os.path.isdir(path):
			temp_created = True
			fd, path     = tempfile.mkstemp(suffix=tmpsuffix,prefix=tmpprefix)
			os.write(fd, engine.ensure_bytes(text))
			os.close(fd)
			command = command[:-1] + [path]
		else:
			temp_created = False
		cmd     = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		data    = cmd.stdout.read()
		error   = cmd.stderr.read()
		cmd.wait()
		# If we have a resolveData attribute, we use it to resolve/correct the
		# data
		if not data and resolveData:
			data = resolveData()
		if temp_created:
			os.unlink(path)
		if not data and not allowEmpty:
			raise Exception(error or "No data")
		if cache is CACHE:
			cache.set(path,timestamp,data)
		elif cache is MEMORY_CACHE:
			cache.set(sig,data)
	return engine.ensure_unicode(data)

def processSugar( text, path, cache=True, includeSource=False ):
	if os.path.isdir(path or "."):
		parent_path  = path or "."
	else:
		parent_path  = os.path.dirname(os.path.abspath(path or "."))
	sugar2 = None
	# try:
	# 	import sugar2
	# except ImportError, e:
	# 	sugar2 = None
	# 	pass
	if sugar2:
		# If Sugar2 is available, we'll use it
		command = sugar2.SugarCommand("sugar2")
		arguments = [
			"-cljs",
			"--cache",
			"--include-source" if includeSource else ""
			"-L" + parent_path,
			"-L" + os.path.join(parent_path, "lib", "sjs"),
			path
		]
		return command.runAsString (arguments), "text/javascript"
	else:
		# Otherwise we fallback to the regular Sugar, which has to be
		# run through popen (so it's slower)
		command = [
			getCommands()["sugar"],
			"-cSljs" if includeSource else "-cljs",
			"-L" + parent_path,
			"-L" + os.path.join(parent_path, "lib", "sjs"),
			path
		]
		return _processCommand(command, text, path, cache), "text/javascript"

def processCoffeeScript( text, path, cache=True ):
	command = [
		getCommands()["coffee"],"-cp",
		path
	]
	return _processCommand(command, text, path, cache), "text/javascript"

def processBabelJS( text, path, cache=True ):
	command = [
		getCommands()["babel"],
		path
	]
	return _processCommand(command, text, path, cache), "text/javascript"

def processTypeScript( text, path, cache=True ):
	temp_path = tempfile.mktemp(prefix="pamelaweb-", suffix=".ts.js")
	command = [
		getCommands()["typescript"], "--outFile", temp_path,
		path
	]
	def read_file():
		if os.path.exists(temp_path):
			with file(temp_path) as f:
				return f.read()
		return None
	# NOTE: We bypass caching for now
	v = _processCommand(command, text, path, cache=True, resolveData=read_file)
	t = None
	# NOTE: TypeScript does not support output to stdout
	if os.path.exists(temp_path):
		with file(temp_path) as f:
			t = f.read()
		os.unlink(temp_path)
	return t,"text/javascript"

def processPandoc( text, path, cache=True ):
	command = [
		getCommands()["pandoc"],
		path
	]
	return PANDOC_HEADER + _processCommand(command, text, path, cache) + PANDOC_FOOTER, "text/html"

def processPythonicCSS( text, path, cache=True ):
	# NOTE: Disabled until memory leaks are fixes
	# import pythoniccss
	# result = pythoniccss.convert(text)
	# return result, "text/css"
	command = [
		getCommands()["pythoniccss"],
		path
	]
	return _processCommand(command, text, path, cache), "text/css"

def processNobrackets( text, path, cache=True ):
	"""Processes the given `text` (that might come from the given path)
	through nobrackets. Nobrackets will in turn invoke sub-processors
	based on the `path` extension."""
	# We ensure that NOBRACKETS references a nobrackets processor,
	# and is properly initialized.
	global NOBRACKETS
	if not NOBRACKETS:
		import nobrackets
		p   = nobrackets.Processor()
		p.registerExtensions(nobrackets)
		NOBRACKETS = p
	# Now we try to retrieve either the text or the path from
	# the cache.
	cache, is_same, data, cache_key = cacheGet (text, path, cache)
	cache_path = path
	if (not is_same) or (not cache):
		# If the contents has changed, or if we did not cache, we'll
		# process the text/path through nobrackets and create an output
		assert path, "Nobrackets is only supported for files, for now"
		res      = NOBRACKETS.processPath(path)
		# We trim the path from the .nb extension, retrieve the actual
		# extension and write the result to a temp file with the
		# proper extension
		path     = NOBRACKETS.trimExtension(path)
		ext      = path.rsplit(".",1)[-1]
		res_path = "{0}/temp-nobrackets-{1}".format(os.path.dirname(os.path.abspath(path)), os.path.basename(path))
		with file(res_path, "w") as f: f.write(res)
		# We not look in the processors for a matching processor
		proc = getProcessors()
		if ext in proc:
			# We don't want to cache here as we're already doing the cachgin
			res, content_type = proc[ext](res, res_path, cache=False)
			os.unlink(res_path)
		else:
			content_type = "text/plain"
		# Now for caching-friendlyness, we store the content_type in addition
		# to the data
		data = content_type + "\t" + res
		if   cache is CACHE:
			cache.set(cache_path, cache_key, data)
		elif cache is MEMORY_CACHE:
			cache.set(cache_key, data)
		return res, content_type
	else:
		# We can retrieve the content from the cache
		content_type, data = data.split("\t", 1)
		return data, content_type

def getProcessors():
	"""Returns a dictionary with the Retro LocalFiles processors already
	setup."""
	global PROCESSORS
	if not PROCESSORS:
		PROCESSORS = {
			"paml"  : processPamela,
			"sjs"   : processSugar,
			"js6"   : processBabelJS,
			"ccss"  : processCleverCSS,
			"coffee": processCoffeeScript,
			"ts"    : processTypeScript,
			"pcss"  : processPythonicCSS,
			"md"    : processPandoc,
			"nb"    : processNobrackets,
		}
	return PROCESSORS

def getLocalFiles(root=""):
	"""Returns a Retro LocalFile component initialized with the Pamela
	processor."""
	return LocalFiles(root=root,processors=getProcessors(),optsuffix=[".paml",".html"], lastModified=False)

def beforeRequest( request ):
	pass

def run( arguments, options={} ):
	files   = getLocalFiles()
	comps   = [files]
	proxies = [x[len("proxy:"):] for x in [x for x in arguments if x.startswith("proxy:")]]
	comps.extend(proxy.createProxies(proxies))
	app     = retro.Application(components=comps)
	#app.onRequest(beforeRequest)
	retro.command(
		arguments,
		app      = app,
		port     = int(options.get("port") or retro.DEFAULT_PORT)
	)

# -----------------------------------------------------------------------------
#
# Main
#
# -----------------------------------------------------------------------------

if __name__ == "__main__":
	options = {}
	if hasattr(engine.logging, "REPORTER"):
		engine.logging.register(engine.logging.StderrReporter())
	for a in sys.argv[1:]:
		a=a.split("=",1)
		if len(a) == 1: v=True
		else: v=a[1];a=a[0]
		options[a.lower()] = v
	run(sys.argv[1:], options)

# EOF - vim: tw=80 ts=4 sw=4 noet
