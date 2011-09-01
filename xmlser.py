# Copyright 2011 Mark Nevill
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
from xml.sax.saxutils import escape
import re
import sys
import collections

class SerializationFormatError(ValueError):
    def __init__(self, msg, fmt, idx):
        self.fmt = fmt
        self.idx = idx
        ValueError.__init__(self, "%s at %d around %r, %r" % (msg, idx, fmt[max(idx-10, 0):idx], fmt[idx:idx+10]))

class InvalidAttribute(SerializationFormatError):
    def __init__(self, fmt, idx, msg=None):
        SerializationFormatError.__init__(self, msg or "Invalid attribute", fmt, idx)

class InvalidValue(SerializationFormatError):
    def __init__(self, fmt, idx, msg=None):
        SerializationFormatError.__init__(self, msg or "Invalid value", fmt, idx)

class InvalidRepetition(SerializationFormatError):
    def __init__(self, fmt, idx, msg=None):
        SerializationFormatError.__init__(self, msg or "Invalid repetition", fmt, idx)

class InvalidName(SerializationFormatError):
    def __init__(self, fmt, idx, msg=None):
        SerializationFormatError.__init__(self, msg or "Invalid name", fmt, idx)

class InvalidTag(SerializationFormatError):
    def __init__(self, fmt, idx, msg=None):
        SerializationFormatError.__init__(self, msg or "Invalid tag", fmt, idx)

class InvalidCondition(SerializationFormatError):
    def __init__(self, fmt, idx, msg=None):
        SerializationFormatError.__init__(self, msg or "Invalid condition", fmt, idx)

def force_unicode(txt):
    try:
        return unicode(txt)
    except UnicodeDecodeError:
        pass
    orig = txt
    if type(txt) != str:
        txt = str(txt)
    for args in [('utf-8',), ('latin1',), ('ascii', 'replace')]:
        try:
            return txt.decode(*args)
        except UnicodeDecodeError:
            pass
    raise ValueError("Unable to force %s object %r to unicode" % (type(orig).__name__, orig))

def compose(*funcs):
    tail = reduce(lambda f1, f2: (lambda v: f1(f2(v))), funcs[:-1])
    return lambda *args, **kwargs: tail(funcs[-1](*args, **kwargs))

_xml_tag_badchr_re = re.compile('[<>&"\']|\\s')
def check_tag(t):
    if not t:
        raise ValueError("XML tag must not be empty")
    if t[0].isdigit():
        raise ValueError("XML tag must not start with a digit")
    if t[:3].lower() == "xml":
        raise ValueError("XML tag must not start with \"xml\"")
    if _xml_tag_badchr_re.search(t):
        raise ValueError("XML tag must not contain special characters")
    return t

def check_attr(a):
    if not a:
        raise ValueError("XML attribute name must not be empty")
    if not a[0].isalpha() and a[0] not in '_:':
        raise ValueError("XML attribute name must start with a letter, underscore or colon")
    if not all(c.isalnum() or c in '_:.-' for c in a[1:]):
        raise ValueError("XML attribute name contains invalid characters")
    return a

class _ListStream(object):
    """Used as "stream" for unicode characters (StringIO et al require bytes)"""
    def __init__(self):
        self.parts = []
        self._val = None
    def write(self, val):
        self.parts.append(val)
        self._val = None
    def getvalue(self):
        if self._val is None:
            self._val = ''.join(self.parts)
        return self._val
    def close(self):
        self._val = None
        self._parts = []

class StreamWriteEncoder(object):
    """Wrapper around streams that encodes unicode characters before writing them"""
    def __init__(self, stream, encoding=None):
        self.stream = stream
        self.encoding = encoding
        if not encoding:
            self.encoding = sys.getfilesystemencoding()

    def write(self, obj):
        if isinstance(obj, unicode):
            self.stream.write(obj.encode(self.encoding))
        else:
            self.stream.write(obj)

    def __getattr__(self, attr):
        return getattr(self.stream, attr)

class Element(collections.namedtuple('Element', 'tag attrs content')):
    def write_xml(self, unicode_stream):
        unicode_stream.write(u'<')
        unicode_stream.write(self.tag)

        for attr in self.attrs:
            unicode_stream.write(u' ')
            unicode_stream.write(attr[0])
            unicode_stream.write(u'="')
            unicode_stream.write(attr[1])
            unicode_stream.write(u'"')

        unicode_stream.write(u'>')

        for child in self.content:
            if hasattr(child, 'write_xml'):
                child.write_xml(unicode_stream)
            else:
                unicode_stream.write(child)

        unicode_stream.write(u'</')
        unicode_stream.write(self.tag)
        unicode_stream.write(u'>')

class AttrLookup(object):

    def __init__(self, keys):
        self.keys = keys or []

    def _lookup(self, obj, key):
        if type(key) == int:
            # int, try to use as index, then key
            try:
                return obj[key]
            except KeyError:
                return obj[str(key)]
            except IndexError as e:
                raise KeyError(str(e))
        else:
            # lookup as key if possible, else attribute
            if hasattr(obj, "__getitem__"):
                try:
                    return obj[key]
                except TypeError:
                    pass
            return getattr(obj, key)

    def __call__(self, obj):
        return reduce(self._lookup, self.keys, obj)

class Literal(object):

    def __init__(self, value):
        self.value = value

    def __call__(self, obj):
        return self.value

class List(object):
    def __init__(self, handler):
        self.handler = handler

    def __call__(self, obj):
        value = self.handler(obj)
        if hasattr(value, 'items'):
            return value.items()
        elif type(value) == int:
            return list(range(value))
        else:
            return value

class Group(object):
    def __init__(self, lookup, handlers):
        self.lookup = lookup
        self.handlers = handlers

    def __call__(self, obj, cur):
        obj = self.lookup(obj)
        for handler in self.handlers:
            handler(obj, cur)

class Conditional(object):
    def __init__(self, lhs, op, rhs, iftrue, iffalse):
        self.lhs, self.op, self.rhs = lhs, op, rhs
        self.iftrue, self.iffalse = iftrue, iffalse

    def __call__(self, obj, cur):
        if self.rhs:
            res = self.op(self.lhs(obj), self.rhs(obj))
        else:
            res = self.op(self.lhs(obj))
        if res:
            self.iftrue(obj, cur)
        elif self.iffalse is not None:
            self.iffalse(obj, cur)

class Attribute(object):
    def __init__(self, attr, value):
        self.attr, self.value = attr, value

    def __call__(self, obj, cur):
        cur.attrs.append((check_attr(force_unicode(self.attr(obj))), escape(force_unicode(self.value(obj)))))

class Text(object):
    def __init__(self, text):
        self.text = text

    def __call__(self, obj, cur):
        cur.content.append(escape(force_unicode(self.text(obj))))

class Tag(object):
    def __init__(self, name, handlers):
        self.name, self.handlers = name, handlers

    def __call__(self, obj, cur):
        tag = Element(check_tag(force_unicode(self.name(obj))), [], [])
        for handler in self.handlers:
            handler(obj, tag)
        if cur:
            cur.content.append(tag)
        else:
            return tag

class Repetition(object):
    def __init__(self, replist, handler):
        self.replist, self.handler = replist, handler

    def __call__(self, obj, cur):
        cur_ = cur
        if not cur:
            cur_ = Element(":", [], [])
        items = self.replist(obj)
        for item in items:
            self.handler(item, cur)
        if not cur:
            return cur_.content

class Fragment(object):
    def __init__(self, handlers):
        self.handlers = handlers

    def __call__(self, obj):
        parent = Element(":", [], [])
        for handler in self.handlers:
            handler(obj, parent)

        return parent.content

class Document(object):
    def __init__(self, handler):
        self.handler = handler

    def __call__(self, obj):
        parent = Element(":", [], [])
        self.handler(obj, parent)
        return parent.content[0]

class Compiler(object):

    _ops = '<=&{~'
    _ends = '>}'
    _vals = '?."'
    _special = '*'+_vals+_ops+_ends

    def __init__(self, fmt):
        self.fmt = fmt

    def _quoted(self, idx):
        assert self.fmt[idx] == '"'
        idx += 1
        beg = idx
        while self.fmt[idx] != '"':
            if self.fmt[idx] == '\\':
                # skip escaped characters
                idx += 1
            idx += 1
        # decode escapes
        return idx+1, self.fmt[beg:idx].decode('string_escape')

    def _get(self, idx):

        if self.fmt[idx].isalpha():
            # identifier, could be dict key or attribute
            beg = idx
            while self.fmt[idx].isalnum() or self.fmt[idx] == '_':
                idx += 1
            return idx, self.fmt[beg:idx]

        elif self.fmt[idx].isdigit():
            # number, could be dict key or index
            beg = idx
            while self.fmt[idx].isdigit():
                idx += 1
            return idx, int(self.fmt[beg:idx])

        elif self.fmt[idx] == '"':
            return self._quoted(idx)

        else:
            raise InvalidAttribute(self.fmt, idx)

    def _val(self, idx, **opts):
        opts.setdefault('strings', True) # allow string values
        opts.setdefault('unquoted', True) # allow unquoted literals (unquoted strings, numbers)
        opts.setdefault('numbers', True) # allow numbers
        assert len(opts) == 3

        if self.fmt[idx] == '.':
            # lookup
            lookup = []
            while self.fmt[idx] == '.':
                idx, key = self._get(idx+1)
                lookup.append(key)
            return idx, AttrLookup(lookup)

        elif self.fmt[idx] == '?':
            # identity
            return idx+1, AttrLookup([])

        elif opts['strings'] and self.fmt[idx] == '"':
            # quoted string literal
            idx, val = self._quoted(idx)
            return idx, Literal(val)

        elif opts['strings'] and opts['unquoted'] and self.fmt[idx].isalpha():
            # unquoted string literal
            beg = idx
            while self.fmt[idx] not in self._special and not self.fmt[idx].isspace():
                idx += 1
            return idx, Literal(self.fmt[beg:idx])

        elif opts['numbers'] and opts['unquoted'] and self.fmt[idx].isdigit():
            # number, but only when nums=True
            beg = idx
            while self.fmt[idx].isdigit():
                idx += 1
            return idx, Literal(int(self.fmt[beg:idx]))

        else:
            raise InvalidValue(self.fmt, idx)

    def _list(self, idx):

        idx, value = self._val(idx, strings=False)
        return idx, List(value)

    def _attr(self, idx):

        idx, attr = self._val(idx, numbers=False)
        idx, val = self._val(idx, unquoted=False)

        return idx, Attribute(attr, val)

    def _text(self, idx):

        idx, text = self._val(idx, numbers=False)
        return idx, Text(text)

    def _group(self, idx):

        lookup = []
        while self.fmt[idx] == '.':
            idx, key = self._get(idx+1)
            lookup.append(key)

        handlers = []
        while self.fmt[idx] != '}':
            idx, handler = self._intag(idx)
            handlers.append(handler)
        idx += 1

        return idx, Group(AttrLookup(lookup), handlers)

    def _cond(self, idx):

        negate = False
        if self.fmt[idx] == '!':
            negate = True
            idx += 1

        idx, lhs = self._val(idx, strings=False)

        import operator
        binary, op = {
            '?': (False, operator.truth),
            '=': (True, operator.eq),
            '<': (True, operator.lt),
            '>': (True, operator.gt),
            '/': (True, operator.contains),
        }.get(self.fmt[idx], (False, None))
        if op is None:
            raise InvalidCondition(self.fmt, idx, "Unrecognized conditional operator")
        idx += 1

        if negate:
            op = compose(operator.not_, op)

        rhs = None
        if binary:
            idx, rhs = self._val(idx)

        idx, iftrue = self._intag(idx)

        iffalse = None
        if self.fmt[idx] == '~':
            idx, iffalse = self._intag(idx+1)

        return idx, Conditional(lhs, op, rhs, iftrue, iffalse)

    def _intag(self, idx):

        if self.fmt[idx] == '<':
            return self._tag(idx+1)

        elif self.fmt[idx] == '=':
            return self._attr(idx+1)

        elif self.fmt[idx] == '&':
            return self._text(idx+1)

        elif self.fmt[idx] == '{':
            return self._group(idx+1)

        elif self.fmt[idx] == '~':
            return self._cond(idx+1)

        else:
            raise InvalidTag(self.fmt, idx, "Unrecognized character %s" % self.fmt[idx])

    def _tag(self, idx, single=False):

        idx, name = self._val(idx, numbers=False)

        replist = None
        if self.fmt[idx] == '*' and single:
            raise InvalidTag(self.fmt, idx, "Root tag cannot be repeated")
        if self.fmt[idx] == '*':
            idx, replist = self._list(idx+1)

        handlers = []
        while self.fmt[idx] != '>':
            idx, handler = self._intag(idx)
            handlers.append(handler)
        idx += 1

        tag = Tag(name, handlers)

        if replist is None:
            return idx, tag
        else:
            return idx, Repetition(replist, tag)

    def compile(self, single_root=True):
        idx = 0
        handlers = []

        try:
            if single_root and self.fmt[idx] == '<':
                idx, handler = self._tag(idx+1, True)
                handlers = [handler]
            else:
                while self.fmt[idx] == '<':
                    idx, handler = self._tag(idx+1, single_root)
                    handlers.append(handler)
        except IndexError:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            raise SerializationFormatError("Unexpected end of format", self.fmt, len(self.fmt)), None, exc_traceback

        if idx != len(self.fmt):
            raise SerializationFormatError("Unprocessed tail", self.fmt, idx)
        if single_root:
            assert len(handlers) == 1
            return Document(handlers[0])
        else:
            return Fragment(handlers)

    def __call__(self, single_root=True):
        return self.compile(single_root)

def write_document(tree, stream=None, encoding=None):
    """
    If a stream is given, the result is encoded (encoding defaults to
    sys.getfilesystemencoding) and written to the stream.

    If no stream is given, the result is returned, either as a unicode
    string or encoded using the requested encoding.
    """

    if stream is None and encoding is None:
        _stream = _ListStream()
    elif stream is None:
        try:
            from cStringIO import StringIO as sio
        except ImportError:
            from StringIO import StringIO as sio
        _stream = StreamWriteEncoder(sio(), encoding)
    else:
        if encoding is None:
            encoding = sys.getfilesystemencoding()
        _stream = StreamWriteEncoder(stream, encoding)

    if encoding is not None and isinstance(tree, Document):
        _stream.write('<?xml version="1.0" encoding="%s"?>' % encoding)
    tree.write_xml(_stream)

    if stream is None:
        res = _stream.getvalue()
        _stream.close()
        return res

def serialize(fmt, obj, stream=None, encoding=None):
    if not hasattr(fmt, 'compile'):
        fmt = Compiler(fmt)
    builder = fmt.compile()
    return write_document(builder(obj), stream, encoding)

def make_serializer(fmt):
    if not hasattr(fmt, 'compile'):
        fmt = Compiler(fmt)
    builder = fmt.compile()
    def serialize(obj, stream=None, encoding=None):
        return write_document(builder(obj), stream, encoding)
    return serialize
