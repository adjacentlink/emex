#
# Copyright (c) 2023 - Adjacent Link LLC, Bridgewater, New Jersey
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in
#   the documentation and/or other materials provided with the
#   distribution.
# * Neither the name of Adjacent Link LLC nor the names of its
#   contributors may be used to endorse or promote products derived
#   from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# See toplevel COPYING for more information.
from collections import namedtuple
import logging

from lxml import etree

schema_xml="""\
<xs:schema xmlns:xs='http://www.w3.org/2001/XMLSchema'>
  <xs:element name='emex-monitor-tag-map'>
    <xs:complexType>
      <xs:sequence>
        <xs:element name='nem'>
          <xs:complexType>
            <xs:sequence>
              <xs:element name='map' minOccurs='0' maxOccurs='unbounded'>
                <xs:complexType>
                  <xs:attribute name='tag' type='xs:string' use='required'/>
                  <xs:attribute name='nem' type='xs:unsignedShort' use='required'/>
                </xs:complexType>
              </xs:element>
            </xs:sequence>
          </xs:complexType>
        </xs:element>
        <xs:element name='ip-address'>
          <xs:complexType>
            <xs:sequence>
              <xs:element name='map' minOccurs='0' maxOccurs='unbounded'>
                <xs:complexType>
                  <xs:attribute name='tag' type='xs:string' use='required'/>
                  <xs:attribute name='ip-address' type='xs:string' use='required'/>
                </xs:complexType>
              </xs:element>
            </xs:sequence>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>"""

TagMap = namedtuple('TagMap', ['tag_to_nem', 'nem_to_tag', 'tag_to_ipaddress', 'ipaddress_to_tag'])

def parse_tag_mapfile(tag_map):
    tag_to_nem = {}
    nem_to_tag = {}
    tag_to_ipaddress = {}
    ipaddress_to_tag = {}

    if not tag_map:
        return TagMap({},{},{},{})

    tree = etree.parse(tag_map)

    root = tree.getroot()

    schemaDoc = etree.fromstring(schema_xml)

    schema = etree.XMLSchema(etree=schemaDoc,attribute_defaults=True)

    if not schema(root):
        message = ""
        for entry in schema.error_log:
            logging.error(entry)
            exit(1)

    for e_map in root.xpath('/emex-monitor-tag-map/nem/map'):
        tag = e_map.get('tag')
        nem = int(e_map.get('nem'))
        tag_to_nem[tag] = nem
        nem_to_tag[nem] = tag

    for e_map in root.xpath('/emex-monitor-tag-map/ip-address/map'):
        tag = e_map.get('tag')
        ipaddress = e_map.get('ip-address')
        tag_to_ipaddress[tag] = ipaddress
        ipaddress_to_tag[ipaddress] = tag

    return TagMap(tag_to_nem,nem_to_tag,tag_to_ipaddress,ipaddress_to_tag)
