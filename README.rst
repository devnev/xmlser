===========================================
xmlser - Fomat String for XML Serialization
===========================================

.. Copyright 2011 Mark Nevill
  
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
  
       http://www.apache.org/licenses/LICENSE-2.0
  
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

What's this About?
==================

xmlser is a python library that makes generating XML less painful.

Generating XML from python objects can and will never be as easy as generating
JSON or YAML without heavy restriction on the resulting XML. Instead, this
library uses specialized format strings allowing terse expression of the desired
transformation from a known python object structure.

Diving In
=========

The Basics
----------

To run the examples below, start off with the following definition::

 >>> import xmlser
 >>> def ser(fmt, obj=None):
 ...     print xmlser.serialize(fmt, obj)

We start off with a plain document containing only two tags::

 >>> ser('<doc<item>>')
 <doc><item></item></doc>

As you can see, the closing tag is dropped by using the greater-than (">")
character as a terminator. So how do we add text elements?

::

 >>> ser('<doc<item&text>>')
 <doc><item>text</item></doc>

Non-ASCII letters can also be used::

 >>> ser(u'<cities<city&東京><city&Zürich>>')
 <cities><city>東京</city><city>Zürich</city></cities>
 >>> # The first city should be Tokyo, someone tell me if I'm wrong

Strings with special characters used by xmlser must be quoted::

 >>> ser(r'<doc<"item.name"&"*=<>?.&~\"\\· ·\t·\n·">>')
 <doc><item.name>*=&lt;&gt;?.&amp;~"\· ·	·
 ·</item.name></doc>
 >>> # Output may differ due to tab

Finally, attributes::

 >>> ser('<doc<item=id"1">>')
 <doc><item id="1"></item></doc>

So far, so good; but not very interesting.

Writing Objects
---------------

There is always a "current" object. It can be displayed using a question mark
("?") as follows::

 >>> ser('<doc<item&?>>', "text & more text")
 <doc><item>text &amp; more text</item></doc>

This lookup can be used in all sorts of places as long as the result is legal
XML::

 >>> ser('<doc<item=?"1"><item=id?><?>>', "name")
 <doc><item name="1"></item><item id="name"></item><name></name></doc>
 >>> ser('<doc<item=?"1">>', "a&b")
 ValueError: XML attribute name contains invalid characters

Looking Up Values
-----------------

Attribute, key and index lookups can be performed using the dot (".") operator::

 >>> ser('<doc<item&.content>>', {"content": "Ich habe eine Nase!"})
 <doc><item>Ich habe eine Nase!</item></doc>
 >>> ser('<doc<item&.0>>', ["Chuchichästli"])
 <doc><item>Chuchichästli</item></doc>

They can easily be chained::

 >>> ser('<doc<item&.content.0>>', {"content": ["Kilimanjaro"]})
 <doc><item>Kilimanjaro</item></doc>

When repeatingly accessing sub-objects of an object, a group with a lookup can
shorten things::

 >>> ser('<doc<item&.content.0><item&.content.1>>', {"content": ["Vinson Massif", "Puncak Jaya"]})
 <doc><item>Vinson Massif</item><item>Puncak Jaya</item></doc>
 >>> ser('<doc{.content<item&.0><item&.1>>}>', {"content": ["Vinson Massif", "Puncak Jaya"]})
 <doc><item>Vinson Massif</item><item>Puncak Jaya</item></doc>

Groups will come in handy again for conditionals.

Repeating yourself
------------------

Tag repetition can be performed over any iterable. If the iterable has an "items"
method, it is called and the result is used for iteration. This allows
iteration of mappings as lists of two-element tuples.

Within the repeated tags, the current element from the repetition is the
current object for lookups::

 >>> ser('<longest_rivers<river*?&?>>', [u"النيل", u"Amazonas", u"长/長江"])
 <longest_rivers><river>ﺎﻠﻨﻴﻟ</river><river>Amazonas</river><river>长/長江</river></longest_rivers>
 >>> ser('<person<.0*?&.1>>', {"fullname": "Thomas Anderson", "title": "Mr.", "nick": "Neo"})
 <person><nick>Neo</nick><fullname>Thomas Anderson</fullname><title>Mr.</title></person>

A notable quirk about repetition is that despite the source iterable coming
after the tag name, lookups in the tag name use the iterated items.

Conditionals
------------

TODO

Exceptions
----------

TODO
