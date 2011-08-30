# -*- coding: utf-8 -*-
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

import xmlser
import unittest

class SerializationTests(unittest.TestCase):

    def cmp_none(self, ser, exp_fmt):
        self.assertEqual(ser.serialize(None), exp_fmt)
        self.assertEqual(ser.serialize([]), exp_fmt)
        self.assertEqual(ser.serialize(1), exp_fmt)
        self.assertEqual(ser.serialize([1]), exp_fmt)

    def cmp_obj(self, ser, exp_fmt):
        self.assertEqual(ser.serialize(None), exp_fmt % None)
        self.assertEqual(ser.serialize(1), exp_fmt % 1)
        self.assertEqual(ser.serialize("a"), exp_fmt % "a")
        self.assertEqual(ser.serialize(u"ä"), exp_fmt % u"ä")

    def cmp_dictitem(self, ser, exp_fmt):
        self.assertEqual(ser.serialize({'item':None}), exp_fmt % None)
        self.assertEqual(ser.serialize({'item':1}), exp_fmt % 1)
        self.assertEqual(ser.serialize({'item':"a"}), exp_fmt % "a")
        self.assertEqual(ser.serialize({'item':u"ä"}), exp_fmt % u"ä")

    def cmp_listitem(self, ser, exp_fmt):
        ser_ = ser
        for i in xrange(0, 5):
            ser = xmlser.Serializer(ser_ % dict(idx=i))
            for o in (None, 1, "a", u"ä"):
                l = [None]*i + [o]
                self.assertEqual(ser.serialize(l), exp_fmt % dict(obj=o))

    def test_root(self):
        ser = xmlser.Serializer("<root>")
        exp = "<root></root>"
        self.cmp_none(ser, exp)

    def test_sub(self):
        ser = xmlser.Serializer("<root<sub>>")
        exp = "<root><sub></sub></root>"
        self.cmp_none(ser, exp)

    def test_3sub(self):
        ser = xmlser.Serializer("<root<sub*3>>")
        exp = "<root><sub></sub><sub></sub><sub></sub></root>"
        self.cmp_none(ser, exp)

    def test_attr_lit(self):
        ser = xmlser.Serializer("<root<sub=attr\"test\">>")
        exp = "<root><sub attr=\"test\"></sub></root>"
        self.cmp_none(ser, exp)

    def test_attr_obj(self):
        ser = xmlser.Serializer("<root<sub=attr?>>")
        exp = u"<root><sub attr=\"%s\"></sub></root>"
        self.cmp_obj(ser, exp)

    def test_attr_dictitem(self):
        ser = xmlser.Serializer("<root<sub=attr.item>>")
        exp = u"<root><sub attr=\"%s\"></sub></root>"
        self.cmp_dictitem(ser, exp)

    def test_attr_listitem(self):
        ser = "<root<sub=attr.%(idx)s>>"
        exp = u"<root><sub attr=\"%(obj)s\"></sub></root>"
        self.cmp_listitem(ser, exp)

    def test_content_lit(self):
        ser = xmlser.Serializer("<root&\"test\">")
        exp = u"<root>test</root>"
        self.cmp_none(ser, exp)

    def test_content_obj(self):
        ser = xmlser.Serializer("<root&?>")
        exp = u"<root>%s</root>"
        self.cmp_obj(ser, exp)

    def test_content_dictitem(self):
        ser = xmlser.Serializer("<root&.item>")
        exp = u"<root>%s</root>"
        self.cmp_dictitem(ser, exp)

    def test_content_listitem(self):
        ser = "<root&.%(idx)s>"
        exp = u"<root>%(obj)s</root>"
        self.cmp_listitem(ser, exp)

    def test_rep_list(self):
        ser = xmlser.Serializer("<root<sub*?&?>>")
        self.assertEqual(ser.serialize(['a', 'b']), "<root><sub>a</sub><sub>b</sub></root>")

    def test_rep_dict(self):
        ser = xmlser.Serializer("<root<sub*?=k.0=v.1>>")
        self.assertEqual(ser.serialize({'a':1, 'b':2}),
                         '<root><sub k="a" v="1"></sub><sub k="b" v="2"></sub></root>')

    def test_sub_dicttag(self):
        ser = xmlser.Serializer("<root<~?&?>>")
        self.assertEqual(ser.serialize({'a':1}), "<root><a>1</a></root>")

    def test_ind_tag(self):
        ser = xmlser.Serializer("<?>")
        self.assertEqual(ser.serialize('a'), "<a></a>")

    def test_ind_attr(self):
        ser = xmlser.Serializer('<root=?"test">')
        self.assertEqual(ser.serialize('a'), '<root a="test"></root>')

if __name__ == "__main__":
    unittest.main()
