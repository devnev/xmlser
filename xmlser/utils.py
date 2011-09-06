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

import sys

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

class ListStream(object):
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

