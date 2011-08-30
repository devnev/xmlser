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

_xml_tag_chr_re = re.compile('[<>&"\']|\\s')
def check_tag(t):
    if not t:
        raise ValueError("XML tag must not be empty")
    if t[0].isdigit():
        raise ValueError("XML tag must not start with a digit")
    if t[:3].lower() == "xml":
        raise ValueError("XML tag must not start with \"xml\"")
    if _xml_tag_chr_re.search(t):
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

_skip = "__skip"

_Element = collections.namedtuple('Element', 'tag attrs content')

class Serializer(object):

    _special = '*=<>?.&~"'
    _xml_special = '& \t\n<>"'

    def __init__(self, fmt):
        self.fmt = fmt
        super(Serializer, self).__init__()

    def _get(self, idx, obj):
        if self.fmt[idx].isalpha():
            attr = ""
            while self.fmt[idx].isalnum() or self.fmt[idx] == '_':
                attr += self.fmt[idx]
                idx += 1
            if obj is _skip:
                return idx, _skip
            if isinstance(obj, dict):
                return idx, obj[attr]
            else:
                return idx, getattr(obj, attr)
        elif self.fmt[idx].isdigit():
            num = ""
            while self.fmt[idx].isdigit():
                num += self.fmt[idx]
                idx += 1
            if obj is _skip:
                return idx, _skip
            try:
                return idx, obj[int(num)]
            except KeyError:
                return idx, obj[num]
            except IndexError as e:
                raise KeyError(str(e))
        elif self.fmt[idx] == '?':
            return idx + 1, obj
        else:
            raise InvalidAttribute(self.fmt, idx)

    def _val(self, idx, obj):
        if self.fmt[idx] == '.':
            while self.fmt[idx] == '.':
                idx, obj = self._get(idx+1, obj)
            return idx, obj
        elif self.fmt[idx] == '"':
            val = ""
            idx += 1
            end = idx
            while self.fmt[end] != '"':
                if self.fmt[end] == '\\':
                    end += 1
                end += 1
            val = self.fmt[idx:end]
            val = val.decode('string_escape')
            return end+1, val
        else:
            raise InvalidValue(self.fmt, idx)

    def _list(self, idx, obj):
        if self.fmt[idx] == '.':
            idx, res = self._get(idx+1, obj)
            if hasattr(res, 'items'):
                res = res.items()
            return idx, res
        elif self.fmt[idx].isdigit():
            num = ""
            while self.fmt[idx].isdigit():
                num += self.fmt[idx]
                idx += 1
            return idx, list(range(int(num)))
        else:
            raise InvalidRepetition(self.fmt, idx)

    def _tag_rest(self, idx, tag, cur, obj):
        try:
            tag = check_tag(force_unicode(tag))
        except ValueError as e:
            raise InvalidName(self.fmt, idx, str(e))

        if self.fmt[idx] == '*' and cur is None:
            raise InvalidRepetition("Cannot repeat root tag")
        if self.fmt[idx] == '*':
            idx += 1
            idx, l = self._list(idx, obj)
        else:
            l = [obj]

        if not l or obj is _skip:
            # empty list, parse to get ending idx but do not use
            e = _Element(tag, [], [])
            idx = self._intag(idx, e, _skip)
        else:
            idx_ = idx
            for item in l:
                e = _Element(tag, [], [])
                idx = idx_
                while self.fmt[idx] != '>':
                    idx = self._intag(idx, e, item)
                if cur is not None:
                    cur.content.append(e)

        if self.fmt[idx] != '>':
            raise InvalidTag(self.fmt, idx, "Tag not terminated with '>'")

        if cur is None:
            return idx + 1, e
        else:
            return idx + 1

    def _tag(self, idx, cur, obj):
        if self.fmt[idx] == '<':
            tag = ""
            idx += 1
            if self.fmt[idx] == '~' and cur is None:
                raise InvalidRepetition("Cannot have multiple root tags")
            if self.fmt[idx] == '~':
                idx += 1
                idx, obj = self._val(idx, obj)
                if not obj or obj is _skip:
                    idx = self._tag_rest(idx, ":", cur, _skip)
                else:
                    idx_ = idx
                    for k, v in obj.iteritems():
                        idx = idx_
                        idx = self._tag_rest(idx, k, cur, v)
                    return idx
            else:
                while self.fmt[idx] not in self._special:
                    tag += self.fmt[idx]
                    idx += 1
                return self._tag_rest(idx, tag, cur, obj)

        else:
            raise InvalidTag(self.fmt, idx)

    def _attr(self, idx, cur, obj):
        assert self.fmt[idx] == '='
        idx += 1
        attr = ""
        if not self.fmt[idx].isalpha():
            raise InvalidName(self.fmt, idx, "Invalid attribute name")
        while self.fmt[idx] not in self._special:
            attr += self.fmt[idx]
            idx += 1
        idx, v = self._val(idx, obj)
        if obj is not _skip:
            cur.attrs.append((check_attr(force_unicode(attr)), escape(force_unicode(v))))
        return idx

    def _intag(self, idx, cur, obj):
        if self.fmt[idx] == '<':
            return self._tag(idx, cur, obj)

        elif self.fmt[idx] == '=':
            return self._attr(idx, cur, obj)

        elif self.fmt[idx] == '&':
            idx += 1
            idx, v = self._val(idx, obj)
            if obj is not _skip:
                cur.content.append(escape(force_unicode(v)))
            return idx

        elif self.fmt[idx] == '>':
            return idx

        else:
            raise InvalidTag(self.fmt, idx, "Unrecognized character %s" % self.fmt[idx])

    def _write(self, stream, tree):

        stream.write(u'<')
        stream.write(tree.tag)

        for attr in tree.attrs:
            stream.write(u' ')
            stream.write(attr[0])
            stream.write(u'="')
            stream.write(attr[1])
            stream.write(u'"')

        stream.write(u'>')

        for child in tree.content:
            if isinstance(child, _Element):
                self._write(stream, child)
            else:
                stream.write(child)

        stream.write(u'</')
        stream.write(tree.tag)
        stream.write(u'>')

    def serialize(self, obj, stream=None, encoding=None):
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

        try:
            idx, tree = self._tag(0, None, obj)
        except IndexError:
            raise SerializationFormatError("Unexpected end of format", self.fmt, len(self.fmt))
        if idx != len(self.fmt):
            raise SerializationFormatError("Tralining format characters", self.fmt, idx)

        if encoding is not None:
            _stream.write('<?xml version="1.0" encoding="%s"?>' % encoding)
        self._write(_stream, tree)
        if stream is None:
            res = _stream.getvalue()
            _stream.close()
            return res

