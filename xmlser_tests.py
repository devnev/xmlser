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

    def cmp_none(self, fmt_or_ser, exp_fmt):
        ser = fmt_or_ser if callable(fmt_or_ser) else xmlser.make_serializer(fmt_or_ser)
        self.assertEqual(ser(None), exp_fmt)
        self.assertEqual(ser([]), exp_fmt)
        self.assertEqual(ser(1), exp_fmt)
        self.assertEqual(ser([1]), exp_fmt)

    def cmp_obj(self, fmt_or_ser, exp_fmt):
        ser = fmt_or_ser if callable(fmt_or_ser) else xmlser.make_serializer(fmt_or_ser)
        self.assertEqual(ser(None), exp_fmt % None)
        self.assertEqual(ser(1), exp_fmt % 1)
        self.assertEqual(ser("a"), exp_fmt % "a")
        self.assertEqual(ser(u"ä"), exp_fmt % u"ä")

    def cmp_dictitem(self, fmt_or_ser, exp_fmt):
        ser = fmt_or_ser if callable(fmt_or_ser) else xmlser.make_serializer(fmt_or_ser)
        self.assertEqual(ser({'item':None}), exp_fmt % None)
        self.assertEqual(ser({'item':1}), exp_fmt % 1)
        self.assertEqual(ser({'item':"a"}), exp_fmt % "a")
        self.assertEqual(ser({'item':u"ä"}), exp_fmt % u"ä")

    def cmp_ser(self, lser, rser, obj):
        lser = xmlser.make_serializer(lser)
        rser = xmlser.make_serializer(rser)
        self.assertEqual(lser(obj), rser(obj))

    def cmp_listitem(self, ser, exp_fmt):
        ser_ = ser
        for i in xrange(0, 5):
            ser = xmlser.make_serializer(ser_ % dict(idx=i))
            for o in (None, 1, "a", u"ä"):
                l = [None]*i + [o]
                self.assertEqual(ser(l), exp_fmt % dict(obj=o))

    def test_root(self):
        ser = xmlser.make_serializer("<root>")
        exp = "<root></root>"
        self.cmp_none(ser, exp)

    def test_sub(self):
        ser = xmlser.make_serializer("<root<sub>>")
        exp = "<root><sub></sub></root>"
        self.cmp_none(ser, exp)

    def test_3sub(self):
        ser = xmlser.make_serializer("<root<sub*3>>")
        exp = "<root><sub></sub><sub></sub><sub></sub></root>"
        self.cmp_none(ser, exp)

    def test_attr_lit(self):
        ser = xmlser.make_serializer("<root<sub=attr\"test\">>")
        exp = "<root><sub attr=\"test\"></sub></root>"
        self.cmp_none(ser, exp)

    def test_attr_obj(self):
        ser = xmlser.make_serializer("<root<sub=attr?>>")
        exp = u"<root><sub attr=\"%s\"></sub></root>"
        self.cmp_obj(ser, exp)

    def test_attr_dictitem(self):
        ser = xmlser.make_serializer("<root<sub=attr.item>>")
        exp = u"<root><sub attr=\"%s\"></sub></root>"
        self.cmp_dictitem(ser, exp)

    def test_attr_listitem(self):
        ser = "<root<sub=attr.%(idx)s>>"
        exp = u"<root><sub attr=\"%(obj)s\"></sub></root>"
        self.cmp_listitem(ser, exp)

    def test_content_lit(self):
        ser = xmlser.make_serializer("<root&\"test\">")
        exp = u"<root>test</root>"
        self.cmp_none(ser, exp)

    def test_content_obj(self):
        ser = xmlser.make_serializer("<root&?>")
        exp = u"<root>%s</root>"
        self.cmp_obj(ser, exp)

    def test_content_dictitem(self):
        ser = xmlser.make_serializer("<root&.item>")
        exp = u"<root>%s</root>"
        self.cmp_dictitem(ser, exp)

    def test_content_listitem(self):
        ser = "<root&.%(idx)s>"
        exp = u"<root>%(obj)s</root>"
        self.cmp_listitem(ser, exp)

    def test_rep_list(self):
        ser = xmlser.make_serializer("<root<sub*?>>")
        self.assertEqual(ser(['a', 'b']), "<root><sub></sub><sub></sub></root>")

    def test_rep_dict(self):
        ser = xmlser.make_serializer("<root<sub*?>>")
        self.assertEqual(ser({'a':1, 'b':2}),
                         '<root><sub></sub><sub></sub></root>')

    def test_sub_dicttag(self):
        ser = xmlser.make_serializer("<root<.0*?>>")
        self.assertEqual(ser({'a':1}), "<root><a></a></root>")

    def test_ind_tag(self):
        ser = xmlser.make_serializer("<?>")
        self.assertEqual(ser('a'), "<a></a>")

    def test_ind_attr(self):
        ser = xmlser.make_serializer('<root=?"test">')
        self.assertEqual(ser('a'), '<root a="test"></root>')

    def test_empty_listrep(self):
        ser = xmlser.make_serializer('<root<sub*?><a>>')
        self.assertEqual(ser([]), '<root><a></a></root>')

    def test_empty_dictrep(self):
        ser = xmlser.make_serializer('<root<sub*?><a>>')
        self.assertEqual(ser({}), '<root><a></a></root>')

    def test_empty_dictkeyrep(self):
        ser = xmlser.make_serializer('<root<.0*?&.1><a>>')
        self.assertEqual(ser({}), '<root><a></a></root>')

    def test_badfmt_space(self):
        for s in ['<root<s ub>>', '<r oot<sub>>', '<root >']:
            self.assertRaises(xmlser.SerializationFormatError, xmlser.make_serializer, s)

    def test_badfmt_notag(self):
        for s in ['<root<&text>>', '<&text>', '<root<<ssub>>']:
            self.assertRaises(xmlser.SerializationFormatError, xmlser.make_serializer, s)

    def test_badfmt_noattrname(self):
        for s in ['<root<=&text>>', '<=&text>', '<root<=<ssub>>>']:
            self.assertRaises(xmlser.SerializationFormatError, xmlser.make_serializer, s)

    def test_badfmt_noattrval(self):
        for s in ['<root<=a&text>>', '<=a&text>', '<root<=a<ssub>>>']:
            self.assertRaises(xmlser.SerializationFormatError, xmlser.make_serializer, s)

    def test_badobj_noattr(self):
        ser = xmlser.make_serializer('<root&.attr>')
        for o, e in [([], AttributeError), ({}, KeyError), (None, AttributeError)]:
            self.assertRaises(e, ser, o)

    def test_badobj_badtag(self):
        for s in ['', ' ', 'xml', 123, '123']:
            try:
                res = xmlser.serialize('<root<?>>', '')
            except xmlser.SerializationFormatError:
                self.fail("Serializing object with valid format string produced SerializationFormatError")
            except ValueError:
                pass
            else:
                self.fail("Serializing object to bad XML %r did not raise an exception" % res)

    def test_badobj_baddictreptag(self):
        for d in [{'':1}, {' ':1}, {'xml':1}, {123:1}, {'123':1}]:
            try:
                res = xmlser.serialize('<root<.0*?&.1>>', d)
            except xmlser.SerializationFormatError:
                self.fail("Serializing object with valid format string produced SerializationFormatError")
            except ValueError:
                pass
            else:
                self.fail("Serializing object to bad XML %r did not raise an exception" % res)

    def test_cond_eqnum_empty(self):
        self.cmp_ser('<root~?=1{}>', '<root>', 1)
        self.cmp_ser('<root~!?=1{}>', '<root>', 1)
        self.cmp_ser('<root~?=1{}>', '<root~?=0{}>', 1)
        self.cmp_ser('<root~?=1{}>', '<root~!?=0{}>', 1)
        self.cmp_ser('<root~1=?{}>', '<root>', 1)
        self.cmp_ser('<root~!1=?{}>', '<root>', 1)
        self.cmp_ser('<root~?=1{}>', '<root~0=?{}>', 1)
        self.cmp_ser('<root~?=1{}>', '<root~!0=?{}>', 1)

    def test_cond_eqnum_tag(self):
        self.cmp_ser('<root~?=1<sub>>', '<root<sub>>', 1)
        self.cmp_ser('<root~?=1<sub>>', '<root>', 0)

    def test_cond_eqquoted(self):
        self.cmp_ser('<root~?=1<sub>>', '<root>', "1")
        self.cmp_ser('<root~?="1"<sub>>', '<root<sub>>', "1")

    def test_cond_truth(self):
        self.cmp_ser('<root~??<sub>>', '<root>', 0)
        self.cmp_ser('<root~??<sub>>', '<root>', "")
        self.cmp_ser('<root~??<sub>>', '<root<sub>>', 1)
        self.cmp_ser('<root~??<sub>>', '<root<sub>>', "1")

    def test_cond_contains(self):
        self.cmp_ser('<root~?/1<sub>>', '<root>', [])
        self.cmp_ser('<root~?/1<sub>>', '<root>', [0])
        self.cmp_ser('<root~?/1<sub>>', '<root<sub>>', [1])

    def test_ifelse_eqnum_empty(self):
        self.cmp_ser('<root~?=1{}~{}>', '<root>', 1)
        self.cmp_ser('<root~!?=1{}~{}>', '<root>', 1)
        self.cmp_ser('<root~?=1{}~{}>', '<root~?=0{}~{}>', 1)
        self.cmp_ser('<root~?=1{}~{}>', '<root~!?=0{}~{}>', 1)
        self.cmp_ser('<root~1=?{}~{}>', '<root>', 1)
        self.cmp_ser('<root~!1=?{}~{}>', '<root>', 1)
        self.cmp_ser('<root~?=1{}~{}>', '<root~0=?{}~{}>', 1)
        self.cmp_ser('<root~?=1{}~{}>', '<root~!0=?{}~{}>', 1)

    def test_ifelse_eqnum_tag(self):
        self.cmp_ser('<root~?=1<true>~<false>>', '<root<true>>', 1)
        self.cmp_ser('<root~?=1<true>~<false>>', '<root<false>>', 0)

if __name__ == "__main__":
    unittest.main()
