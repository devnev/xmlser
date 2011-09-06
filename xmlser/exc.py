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

