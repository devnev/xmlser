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

def write_document(tree, stream=None, encoding=None):
    """
    If a stream is given, the result is encoded (encoding defaults to
    sys.getfilesystemencoding) and written to the stream.

    If no stream is given, the result is returned, either as a unicode
    string or encoded using the requested encoding.
    """
    from . import utils, ast
    import sys

    if stream is None and encoding is None:
        _stream = utils.ListStream()
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
        from . import compiler
        fmt = compiler.Compiler(fmt)
    builder = fmt.compile()
    return write_document(builder(obj), stream, encoding)

def make_serializer(fmt):
    from . import compiler
    if not hasattr(fmt, 'compile'):
        fmt = compiler.Compiler(fmt)
    builder = fmt.compile()
    def serialize(obj, stream=None, encoding=None):
        return write_document(builder(obj), stream, encoding)
    return serialize
