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

# special object used when skipping through the format string, e.g. because a
# list was empty.
_skip = "__skip"

_Element = collections.namedtuple('Element', 'tag attrs content')

class Serializer(object):

    # special characters in format strings
    _special = '*=<>?.&~"'

    def __init__(self, fmt):
        self.fmt = fmt
        super(Serializer, self).__init__()

    def _get(self, idx, obj):
        """After a dot or similar, look up a value"""

        if self.fmt[idx].isalpha():
            # identifier, could be dict key or attribute
            attr = ""
            while self.fmt[idx].isalnum() or self.fmt[idx] == '_':
                attr += self.fmt[idx]
                idx += 1

            # if skipping, do not peform lookup
            if obj is _skip:
                return idx, _skip

            # try to lookup value for attr
            if isinstance(obj, dict):
                return idx, obj[attr]
            else:
                return idx, getattr(obj, attr)

        elif self.fmt[idx].isdigit():
            # number, could be dict key or index
            num = ""
            while self.fmt[idx].isdigit():
                num += self.fmt[idx]
                idx += 1

            # if skipping, do not peform lookup
            if obj is _skip:
                return idx, _skip

            # try to lookup value for num
            try:
                return idx, obj[int(num)]
            except KeyError:
                return idx, obj[num]
            except IndexError as e:
                raise KeyError(str(e))

        else:
            raise InvalidAttribute(self.fmt, idx)

    def _val(self, idx, obj):
        """Get a single value, either from a literal or from a lookup"""

        if self.fmt[idx] == '.':
            # lookup
            while self.fmt[idx] == '.':
                idx, obj = self._get(idx+1, obj)
            return idx, obj

        elif self.fmt[idx] == '?':
            # identity operation
            return idx + 1, obj

        elif self.fmt[idx] == '"':
            # quoted string literal
            val = ""
            idx += 1
            end = idx
            while self.fmt[end] != '"':
                if self.fmt[end] == '\\':
                    # skip escaped characters
                    end += 1
                end += 1
            val = self.fmt[idx:end]
            # decode escapes
            val = val.decode('string_escape')
            return end+1, val

        elif self.fmt[idx].isalpha():
            # unquoted string literal
            val = ""
            while self.fmt[idx] not in self._special and not self.fmt[idx].isspace():
                val += self.fmt[idx]
                idx += 1
            return idx, val

        else:
            raise InvalidValue(self.fmt, idx)

    def _list(self, idx, obj):
        """Get a list for repetition."""

        if self.fmt[idx] == '.':
            # lookup object
            while self.fmt[idx] == '.':
                idx, obj = self._get(idx+1, obj)
            # if its a mapping, get a (key, value) iterable
            if hasattr(obj, 'items'):
                obj = obj.items()
            return idx, obj

        elif self.fmt[idx] == '?':
            # identity operation
            if hasattr(obj, 'items'):
                obj = obj.items()
            return idx + 1, obj

        elif self.fmt[idx].isdigit():
            # repeat a fix number of times
            num = ""
            while self.fmt[idx].isdigit():
                num += self.fmt[idx]
                idx += 1
            return idx, list(range(int(num)))

        else:
            raise InvalidRepetition(self.fmt, idx)

    def _attr(self, idx, cur, obj):
        """Handle an attribute. idx must be on the '='."""

        if self.fmt[idx] != '=':
            raise InvalidAttribute(self.fmt, idx)
        idx += 1

        try:
            idx, attr = self._val(idx, obj)
        except InvalidValue as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            raise InvalidName(e.fmt, e.idx, "Invalid attribute name"), None, exc_traceback

        idx, v = self._val(idx, obj)

        # only actually add the attribute if we're not skipping
        if obj is not _skip:
            cur.attrs.append((check_attr(force_unicode(attr)), escape(force_unicode(v))))

        return idx

    def _intag(self, idx, cur, obj):
        """Handle children and attributes of tag."""

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

    def _tag_rep(self, idx, tag, cur, obj):
        """Handle possible repetition of tag. `cur is None` implies this is the root tag."""

        try:
            tag = check_tag(force_unicode(tag))
        except ValueError as e:
            raise InvalidName(self.fmt, idx, str(e))

        # handle repetition
        if self.fmt[idx] == '*' and cur is None:
            raise InvalidRepetition("Cannot repeat root tag")
        if self.fmt[idx] == '*':
            idx += 1
            idx, l = self._list(idx, obj)
        else:
            l = [obj]

        if not l or obj is _skip:
            # empty list or skipping, parse to get ending idx but do not use
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
            # in special case of root, we return the idx and the element
            return idx + 1, e
        else:
            return idx + 1


    def _tag_keyrep(self, idx, cur, obj):
        """
        Handle dict-based tag generation (key is tag, value is inner object).
        `cur is None` implies this is the root tag.
        """

        tag = ""

        # handle dict-based tag generation
        if self.fmt[idx] == '~' and cur is None:
            raise InvalidRepetition("Cannot have multiple root tags")
        if self.fmt[idx] == '~':
            idx += 1
            idx, obj = self._val(idx, obj)
            if not obj or obj is _skip:
                # empty dict or skipping, parse to get end position but discard
                # ":" is just an arbitrary valid tag name, it is discarded anyway
                return self._tag_rep(idx, ":", cur, _skip)
            else:
                idx_ = idx
                for k, v in obj.iteritems():
                    idx = idx_
                    idx = self._tag_rep(idx, check_tag(force_unicode(k)), cur, v)
                return idx
        else:
            # extract tag name
            try:
                idx, tag = self._val(idx, obj)
            except InvalidValue as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                raise InvalidTag(e.fmt, e.idx, "invalid tag"), None, exc_traceback
            return self._tag_rep(idx, check_tag(force_unicode(tag)), cur, obj)

    def _tag(self, idx, cur, obj):
        """Handle a tag. `cur is None` implies this is the root tag."""

        if self.fmt[idx] != '<':
            raise InvalidTag(self.fmt, idx)

        idx += 1

        return self._tag_keyrep(idx, cur, obj)

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
        """
        Serialize an object to XML using this serializer's format string.

        If a stream is given, the result is encoded (encoding defaults to
        sys.getfilesystemencoding) and written to the stream.

        If no stream is given, the result is returned, either as a unicode
        string or encoded using the requested encoding.

        In any case, if the result is encoded, it is prefixed with an xml
        version tag containing the encoding, e.g. for UTF-8:
            <?xml version="1.0" encoding="UTF-8" ?>
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

