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

import collections
from xml.sax.saxutils import escape
from .utils import force_unicode
import re

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

