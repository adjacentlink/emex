# Copyright (c) 2022,2023 - Adjacent Link LLC, Bridgewater, New Jersey
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of Adjacent Link LLC nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
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
import copy
import math

from emex.antenna import Antenna
from emex.antennaprofile import AntennaProfile
from emex.emoeerror import EmoeError
from emex.platform import Platform
from emex.initialcondition import InitialCondition
from emex.helpers.platforms.nemhelper import NemHelper
from emex.helpers.platforms.ipv4helper import Ipv4Helper
from emex.helpers.platforms.phyhelper import PhyHelper
from emex.utils import load_platform_helpers


class Emoe:
    @staticmethod
    def from_protobuf(emoe_proto, antennatypes, platformtypes):
        emoe = Emoe(emoe_proto.name, [], [])

        for antenna_proto in emoe_proto.antennas:
            emoe.add_antenna(
                Antenna.from_protobuf(antenna_proto, antennatypes))

        platforms = []
        for platform_proto in emoe_proto.platforms:
            platforms.append(Platform.from_protobuf(platform_proto, platformtypes))

        Emoe.configure_and_check_platforms(platforms)

        for platform in platforms:
            emoe.add_platform(platform)

        for intial_condition_proto in emoe_proto.initial_conditions:
            emoe.add_initial_condition(
                InitialCondition.from_protobuf(intial_condition_proto))

        return emoe


    @staticmethod
    def configure_and_check_platforms(platforms):
        helpers=[NemHelper, Ipv4Helper, PhyHelper]

        helpers.extend(load_platform_helpers(platforms))

        # Configuration Helpers
        for helper in helpers:
            helper().configure(platforms)

        for p in platforms:
            if not p.configured:
                unconfigured_str = ', '.join(['.'.join(ucfg)
                                              for ucfg in p.unconfigured()])
                raise EmoeError(
                    f'Platform "{p.name}" has unconfigured parameters ' \
                    f'"{unconfigured_str}".')

        for helper in helpers:
            helper().check(platforms)


    def __init__(self,
                 name,
                 platforms=[],
                 antennas=[],
                 initial_conditions=[]):
        self._name = name

        self.configure_and_check_platforms(platforms)

        # map of (platform_name, component_name) tuples to its corresponding
        # antennaname, north, east and up parameters
        self._antenna_assignments = {}
        self._antennas = {}
        for antenna in antennas:
            self.add_antenna(antenna)

        self._platforms = []
        for platform in platforms:
            self.add_platform(platform)

        self._initial_conditions = []
        for ic in initial_conditions:
            self.add_initial_condition(ic)


    @property
    def name(self):
        return self._name


    @property
    def platforms(self):
        return self._platforms


    def platform_by_name(self, name):
        for platform in self._platforms:
            if name == platform.name:
                return platform
        return None


    @property
    def nemids(self):
        nemids = set([])

        for p in self.platforms:
            nemids.update(p.nemids)

        return sorted(nemids)


    @property
    def initial_conditions(self):
        return self._initial_conditions


    def resources(self, resource):
        return math.ceil(
            sum([p.resources()[resource] for p in self.platforms]))


    @property
    def cpus(self):
        return math.ceil(sum([p.cpus for p in self.platforms]))


    def to_protobuf(self, emoe_proto):
        emoe_proto.name = self._name

        for _,antenna in self._antennas.items():
            antenna.to_protobuf(emoe_proto.antennas.add())

        for platform in self._platforms:
            platform.to_protobuf(emoe_proto.platforms.add())

        for initial_condition in self._initial_conditions:
            initial_condition.to_protobuf(emoe_proto.initial_conditions.add())


    def add_platform(self, platform):
        self._platforms.append(platform)

        for c in platform.components:
            if c.has_param('phy', 'antenna0'):
                # verify that antenna0 is a valid antenna name, either omniGAIN
                # or the name of one of the directional antennas that is part
                # of this emoe
                antennaname = c.get_param('phy', 'antenna0').value[0]

                if antennaname.startswith('omni'):
                    continue

                have_antenna = antennaname in self.antennas

                if not have_antenna:
                    raise EmoeError(
                        f'For platform "{platform.name}" unknown antenna0 name "{antennaname}"')

                north = c.get_param('phy', 'antenna0_north').value[0]
                east = c.get_param('phy', 'antenna0_east').value[0]
                up = c.get_param('phy', 'antenna0_up').value[0]

                antenna = self.antennas[antennaname]

                antenna_key = (platform.name, c.name)

                self._antenna_assignments[antenna_key] = AntennaProfile(antenna, north, east, up)


    def add_antenna(self, antenna):
        # antennas should have unique names
        self._antennas[antenna.name] = antenna


    @property
    def antennas(self):
        return self._antennas


    @property
    def antenna_assignments(self):
        return self._antenna_assignments


    def antenna_assignment(self, platform_name, component_name):
        return self._antenna_assignments.get((platform_name, component_name), None)


    def add_initial_condition(self, initial_condition):
        if not self.platform_by_name(initial_condition.platform_name):
            raise EmoeError(
                f'Unknown platform "{initial_condition.platform_name}" in initial conditions.')

        self._initial_conditions.append(initial_condition)


    def __str__(self):
        s = '=====================\n'
        s += f'emoe: {self.name}\n'
        s += '=====================\n'
        s += 'antennas:\n'
        s += '---------\n'
        for antennaname in self._antennas:
            s += str(antennaname) + '\n'
        s += '\n'
        s += 'platforms:\n'
        s += '----------\n'
        for platform in self._platforms:
            s += str(platform) + '\n'
        s += 'initial conditions:\n'
        s += '-------------------\n'
        print(self._initial_conditions)
        for initial_condition in self._initial_conditions:
            s += str(initial_condition) + '\n'

        return s
