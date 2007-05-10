#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project           :   Pamela
# -----------------------------------------------------------------------------
# Author            :   Sebastien Pierre                 <sebastien@type-z.org>
# License           :   Lesser Gnu Public License
# -----------------------------------------------------------------------------
# Creation date     :   10-May-2007
# Last mod.         :   10-May-2007
# -----------------------------------------------------------------------------

import os, sys, re
from xml.etree import cElementTree as ET

PAMELA_VERSION = "0.1"

# PAMELA GRAMMAR ______________________________________________________________

SYMBOL_NAME    = "[\w\d_-]+"
SYMBOL_ID_CLS  = "(\#%s|\.%s)+" % (SYMBOL_NAME, SYMBOL_NAME)
SYMBOL_ATTR    = "%s(=[^),]+)?" % (SYMBOL_NAME)
SYMBOL_ATTRS   = "\(%s(,%s)+\)" % (SYMBOL_ATTR, SYMBOL_ATTR)
RE_COMMENT     = re.compile("^#.*$")
RE_EMPTY       = re.compile("^\s*$")
RE_DECLARATION = re.compile("^@(%s):?" % (SYMBOL_NAME))
RE_ELEMENT     = re.compile("^\<((%s)(%s)?|(%s))(%s)?\:?" % (
	SYMBOL_NAME,
	SYMBOL_ID_CLS,
	SYMBOL_ID_CLS,
	SYMBOL_ATTRS
))
RE_LEADING_TAB = re.compile("\t*")
RE_LEADING_SPC = re.compile("[ ]*")

# -----------------------------------------------------------------------------
#
# Formatting function (borrowed from LambdaFactory modelwriter module)
#
# -----------------------------------------------------------------------------

FORMAT_PREFIX = "\t"
def _format( value, level=-1 ):
	"""Format helper operation. See @format."""
	if type(value) in (list, tuple):
		res = []
		for v in value:
			if v is None: continue
			res.extend(_format(v, level+1))
		return res
	else:
		if value is None: return ""
		assert type(value) in (str, unicode), "Unsupported type: %s" % (value)
		return ["\n".join((level*FORMAT_PREFIX)+v for v in value.split("\n"))]

def format( *values ):
	"""Formats a combination of string ang tuples. Strings are joined by
	newlines, and the content of the inner tuples gets indented."""
	return "\n".join(_format(values))

# -----------------------------------------------------------------------------
#
# Writer class
#
# -----------------------------------------------------------------------------

class Writer:
	"""The Writer class implements a simple SAX-like interface to create the
	resulting HTML/XML document. This is not API-compatible with SAX because
	Pamela as slightly differnt information than what SAX offers, which requires
	specific methods."""

	class Text:
		"""Reprensents a text fragment within the HTML document."""
		def __init__(self, content):
			self.content = content
		def asXML(self,pretty=False):
			return self.content
		def asList(self):
			return self.content

	class Element:
		"""Reprensents an element within the HTML document."""
		def __init__(self, name, attributes=None,isInline=False):
			self.name=name
			self.attributes=attributes or []
			self.content=[]
			self.isInline=False
		def append(self,n):
			self.content.append(n)
		def asXML(self,pretty=False):
			content = "".join(c.asXML(pretty) for c in self.content)
			return "<%s>%s</%s>" % (content)
		def asList(self):
			# FIXME: Support div and spans
			if not self.content:
				if self.isInline:
					return "<%s />" % (self.name)
				else:
					return ["<%s />" % (self.name)]
			else:
				return [
					"<%s>" % (self.name),
					list(c.asList() for c in self.content),
					"</%s>" % (self.name)
				]

	class Declaration(Element):
		def __init__(self, name, attributes=None):
			Writer.Element.__init__(self,name,attributes)

	def __init__( self ):
		pass

	def onDocumentStart( self ):
		self._content   = []
		self._nodeStack = []
		self._document = self.Element("document")

	def onDocumentEnd( self ):
		r = "".join(format(c.asList()) for c in self._document.content)
		return r

	def onComment( self, line ):
		line = line.replace("\n", " ").strip()
		#comment = ET.Comment(line)
		#self._node().append(comment)

	def onTextAdd( self, text ):
		self._node().append(self.Text(text))

	def onElementStart( self, name, attributes=None ):
		element = self.Element(name)
		self._node().append(element)
		self._nodeStack.append(element)

	def onElementEnd( self ):
		self._nodeStack.pop()

	def onDeclarationStart( self, name, attributes=None ):
		element = self.Declaration(name)
		self._nodeStack.append(element)

	def onDeclarationEnd( self ):
		self._nodeStack.pop()

	def _node( self ):
		if not self._nodeStack: return self._document
		return self._nodeStack[-1]

# -----------------------------------------------------------------------------
#
# Parser class
#
# -----------------------------------------------------------------------------

class Parser:

	def __init__( self ):
		self._tabsOnly   = False
		self._spacesOnly = False
		self._tabsWidth  = 4
		self._elementStack = []
		self._writer = Writer()

	def parseFile( self, path ):
		# FIXME: File exists and is readable
		f = file(path, "r")
		self._writer.onDocumentStart()
		for l in f.readlines():
			self.parseLine(l)
		return self._writer.onDocumentEnd()

	def parseLine( self, line ):
		"""Parses the given line of text."""
		indent, line = self._getLineIndent(line)
		# First, we make sure we close the elements that may be outside of the
		# scope of this
		# FIXME: Empty lines may have an indent < than the current element they
		# are bound to
		is_empty       = RE_EMPTY.match(line)
		if is_empty:
			return
		is_comment     = RE_COMMENT.match(line)
		# Is it a comment ?
		if is_comment:
			# FIXME: Integrate this
			return
			return self._writer.onComment(line)
		self._gotoParentElement(indent)
		# Is it a declaration ?
		is_declaration = RE_DECLARATION.match(line)
		if is_declaration:
			self._elementStack.append(indent)
			declared_name = is_declaration.group(1)
			self._writer.onDeclarationStart(declared_name)
			return
		# Is it an element ?
		is_element = RE_ELEMENT.match(line)
		if is_element:
			self._elementStack.append(indent)
			groups = is_element.groups()
			self._writer.onElementStart(groups[0])
			return
		# Otherwise it's data
		self._writer.onTextAdd(line.replace("\n", " "))

	def parseContentLine( self, line ):
		"""Parses a line that is data/text that is part of an element
		content.""" 

	def _gotoParentElement( self, currentIndent ):
		while self._elementStack and self._elementStack[-1] >= currentIndent:
			self._elementStack.pop()
			self._writer.onElementEnd()

	def _getLineIndent( self, line ):
		"""Returns the line indentation as a number. It takes into account the
		fact that tabs may be requried or not, and also takes into account the
		'tabsWith' property."""
		tabs = RE_LEADING_TAB.match(line)
		spaces = RE_LEADING_SPC.match(line)
		if self._tabsOnly and spaces:
			raise Exception("Tabs are expected, your lines are indented with spaces")
		if self._spacesOnly and tabs:
			raise Exception("Spaces are expected, your lines are indented with tabs")
		if tabs and len(tabs.group()) > 0:
			return len(tabs.group()) * self._tabsWidth, line[len(tabs.group()):]
		elif spaces and len(spaces.group()) > 0:
			return len(spaces.group()), line[len(spaces.group()):]
		else:
			return 0, line

def run( arguments ):
	input_file = arguments[0]
	parser = Parser()
	print parser.parseFile(input_file)

if __name__ == "__main__":
	run(sys.argv[1:])

# EOF

