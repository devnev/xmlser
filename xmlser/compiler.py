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
import sys
from . import ast, exc, utils

class Compiler(object):

    _ops = '<=&{~'
    _ends = '>}'
    _vals = '?."'
    _special = '*/'+_vals+_ops+_ends

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
            raise exc.InvalidAttribute(self.fmt, idx)

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
            return idx, ast.AttrLookup(lookup)

        elif self.fmt[idx] == '?':
            # identity
            return idx+1, ast.AttrLookup([])

        elif opts['strings'] and self.fmt[idx] == '"':
            # quoted string literal
            idx, val = self._quoted(idx)
            return idx, ast.Literal(val)

        elif opts['strings'] and opts['unquoted'] and self.fmt[idx].isalpha():
            # unquoted string literal
            beg = idx
            while self.fmt[idx] not in self._special and not self.fmt[idx].isspace():
                idx += 1
            return idx, ast.Literal(self.fmt[beg:idx])

        elif opts['numbers'] and opts['unquoted'] and self.fmt[idx].isdigit():
            # number, but only when nums=True
            beg = idx
            while self.fmt[idx].isdigit():
                idx += 1
            return idx, ast.Literal(int(self.fmt[beg:idx]))

        else:
            raise exc.InvalidValue(self.fmt, idx)

    def _list(self, idx):

        idx, value = self._val(idx, strings=False)
        return idx, ast.List(value)

    def _attr(self, idx):

        idx, attr = self._val(idx, numbers=False)
        idx, val = self._val(idx, unquoted=False)

        return idx, ast.Attribute(attr, val)

    def _text(self, idx):

        idx, text = self._val(idx, numbers=False)
        return idx, ast.Text(text)

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

        return idx, ast.Group(ast.AttrLookup(lookup), handlers)

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
            raise exc.InvalidCondition(self.fmt, idx, "Unrecognized conditional operator")
        idx += 1

        if negate:
            op = utils.compose(operator.not_, op)

        rhs = None
        if binary:
            idx, rhs = self._val(idx)

        idx, iftrue = self._intag(idx)

        iffalse = None
        if self.fmt[idx] == '~':
            idx, iffalse = self._intag(idx+1)

        return idx, ast.Conditional(lhs, op, rhs, iftrue, iffalse)

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
            raise exc.InvalidTag(self.fmt, idx, "Unrecognized character %s" % self.fmt[idx])

    def _tag(self, idx, single=False):

        idx, name = self._val(idx, numbers=False)

        replist = None
        if self.fmt[idx] == '*' and single:
            raise exc.InvalidTag(self.fmt, idx, "Root tag cannot be repeated")
        if self.fmt[idx] == '*':
            idx, replist = self._list(idx+1)

        handlers = []
        while self.fmt[idx] != '>':
            idx, handler = self._intag(idx)
            handlers.append(handler)
        idx += 1

        tag = ast.Tag(name, handlers)

        if replist is None:
            return idx, tag
        else:
            return idx, ast.Repetition(replist, tag)

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
            raise exc.SerializationFormatError("Unexpected end of format", self.fmt, len(self.fmt)), None, exc_traceback

        if idx != len(self.fmt):
            raise exc.SerializationFormatError("Unprocessed tail", self.fmt, idx)
        if single_root:
            assert len(handlers) == 1
            return ast.Document(handlers[0])
        else:
            return ast.Fragment(handlers)

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
        _stream = utils._ListStream()
    elif stream is None:
        try:
            from cStringIO import StringIO as sio
        except ImportError:
            from StringIO import StringIO as sio
        _stream = utils.StreamWriteEncoder(sio(), encoding)
    else:
        if encoding is None:
            encoding = sys.getfilesystemencoding()
        _stream = utils.StreamWriteEncoder(stream, encoding)

    if encoding is not None and isinstance(tree, ast.Document):
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
