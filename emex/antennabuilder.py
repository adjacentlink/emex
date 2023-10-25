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

import os
from lxml import etree


class AntennaBuilder:
    def __init__(self, antennatypes):
        self._antennatypes = antennatypes

        self._built_antennas = []


    def build(self, antennaprofile, configdir):
        antennatype_name = antennaprofile.antenna.antennatype_name

        if antennatype_name == 'sector':
            return self.build_sector_antenna(antennaprofile, configdir)
        else:
            raise ValueError(f'Unknown antenna type "{antennatype_name}".')


    def build_sector_antenna(self, antennaprofile, configdir):
        antennaprofile_elem = etree.Element('antennaprofile')

        antennapattern_elem = etree.SubElement(antennaprofile_elem, 'antennapattern')

        params = antennaprofile.antenna.params

        vertical_beamwidth = params['vertical_beamwidth'].value[0]
        max_vertical_beamwidth = int(min(90, vertical_beamwidth//2))
        min_vertical_beamwidth = int(-max_vertical_beamwidth)

        horizontal_beamwidth = params['horizontal_beamwidth'].value[0]
        max_horizontal_beamwidth = int(min(90, horizontal_beamwidth//2))
        min_horizontal_beamwidth = int(360 - max_horizontal_beamwidth)

        gain = params['gain'].value[0]

        rejection = params['rejection'].value[0]

        if min_vertical_beamwidth > -90:
            # rejection region top
            elevation_elem = etree.SubElement(antennapattern_elem, 'elevation')
            elevation_elem.set('min', str(-90))
            elevation_elem.set('max', str(min_vertical_beamwidth))
            bearing_elem = etree.SubElement(elevation_elem, 'bearing')
            bearing_elem.set('min', str(0))
            bearing_elem.set('max', str(359))
            gain_elem = bearing_elem = etree.SubElement(bearing_elem, 'gain')
            gain_elem.set('value', str(rejection))

        # sector region middle
        elevation_elem = etree.SubElement(antennapattern_elem, 'elevation')
        elevation_elem.set('min', str(min_vertical_beamwidth+1))
        elevation_elem.set('max', str(max_vertical_beamwidth-1))
        bearing_elem = etree.SubElement(elevation_elem, 'bearing')
        bearing_elem.set('min', str(0))
        bearing_elem.set('max', str(max_horizontal_beamwidth-1))
        gain_elem = bearing_elem = etree.SubElement(bearing_elem, 'gain')
        gain_elem.set('value', str(gain))

        bearing_elem = etree.SubElement(elevation_elem, 'bearing')
        bearing_elem.set('min', str(max_horizontal_beamwidth))
        bearing_elem.set('max', str(min_horizontal_beamwidth))
        gain_elem = bearing_elem = etree.SubElement(bearing_elem, 'gain')
        gain_elem.set('value', str(rejection))

        bearing_elem = etree.SubElement(elevation_elem, 'bearing')
        bearing_elem.set('min', str(min_horizontal_beamwidth+1))
        bearing_elem.set('max', str(359))
        gain_elem = bearing_elem = etree.SubElement(bearing_elem, 'gain')
        gain_elem.set('value', str(gain))

        if max_vertical_beamwidth < 90:
            # rejection region bottom
            elevation_elem = etree.SubElement(antennapattern_elem, 'elevation')
            elevation_elem.set('min', str(max_vertical_beamwidth))
            elevation_elem.set('max', str(90))
            bearing_elem = etree.SubElement(elevation_elem, 'bearing')
            bearing_elem.set('min', str(0))
            bearing_elem.set('max', str(359))
            gain_elem = bearing_elem = etree.SubElement(bearing_elem, 'gain')
            gain_elem.set('value', str(rejection))

        antennaprofile_elem_tree = antennaprofile_elem.getroottree()

        antennaprofile_elem_tree.docinfo.system_url = \
            'file:///usr/share/emane/dtd/antennaprofile.dtd'

        profile_file_name = \
            f'{antennaprofile.name}_north{antennaprofile.north}_east{antennaprofile.east}_up{antennaprofile.up}.xml'
        profile_file = os.path.join(configdir, profile_file_name)
        antennaprofile_elem_tree.write(profile_file, pretty_print=True)

        return profile_file_name
