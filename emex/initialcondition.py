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

from collections import namedtuple

from emex.antenna import Antenna
from emex.emaneeventmessages import POV,Pathloss,AntennaPointing


class InitialCondition:
    @staticmethod
    def from_protobuf(initial_condition_proto):
        # required string platform_name = 1;
        # repeated Pathloss pathlosses = 2;
        # optional POV pov = 3;
        platform_name = initial_condition_proto.platform_name

        pov = None

        if initial_condition_proto.pov:
            # only accept the first value specified (0 or 1 quantifier)
            pov_proto = initial_condition_proto.pov[0]

            pov = POV(component_names = pov_proto.component_names,
                      latitude = pov_proto.latitude,
                      longitude = pov_proto.longitude,
                      altitude = pov_proto.altitude,
                      speed = pov_proto.speed,
                      azimuth = pov_proto.azimuth,
                      elevation = pov_proto.elevation,
                      pitch = pov_proto.pitch,
                      roll = pov_proto.roll,
                      yaw = pov_proto.yaw)

        pathlosses = []

        for pathloss_proto in initial_condition_proto.pathlosses:
            pathlosses.append(Pathloss(component_names=pathloss_proto.component_names,
                                       remote_platform=pathloss_proto.remote_platform_name,
                                       remote_component_names=pathloss_proto.remote_component_names,
                                       pathloss=pathloss_proto.pathloss))

        antenna_pointings = []

        for antenna_pointing_proto in initial_condition_proto.antenna_pointings:
            antenna_pointings.append(
                AntennaPointing(component_names=antenna_pointing_proto.component_names,
                                azimuth=antenna_pointing_proto.azimuth,
                                elevation=antenna_pointing_proto.elevation))

        return InitialCondition(platform_name,
                                pov,
                                pathlosses,
                                antenna_pointings)


    def __init__(self, platform_name, pov=None, pathlosses=[], antenna_pointings=[]):
        self._platform_name = platform_name

        self._pov = pov

        self._pathlosses = pathlosses

        self._antenna_pointings = antenna_pointings


    @property
    def platform_name(self):
        return self._platform_name


    @property
    def pov(self):
        return self._pov


    @pov.setter
    def pov(self, pov):
        self._pov = pov


    @property
    def pathlosses(self):
        return self._pathlosses


    def add_pathloss(self, pathloss):
        self._pathlosses.append(pathloss)


    @property
    def antenna_pointings(self):
        return self._antenna_pointings


    def add_antenna_pointing(self, pointing):
        self._antenna_pointings.append(pointing)


    def to_protobuf(self, initial_condition_proto):
        initial_condition_proto.platform_name = self.platform_name

        if self._pov:
            pov_proto = initial_condition_proto.pov.add()

            for component_name in self._pov.component_names:
                pov_proto.component_names.append(component_name)

            pov_proto.latitude = self._pov.latitude
            pov_proto.longitude = self._pov.longitude
            pov_proto.altitude = self._pov.altitude
            pov_proto.speed = self._pov.speed
            pov_proto.azimuth = self._pov.azimuth
            pov_proto.elevation = self._pov.elevation
            pov_proto.pitch = self._pov.pitch
            pov_proto.roll = self._pov.roll
            pov_proto.yaw = self._pov.yaw

        for pathloss in self._pathlosses:
            pathloss_proto = initial_condition_proto.pathlosses.add()

            pathloss_proto.remote_platform_name = pathloss.remote_platform
            pathloss_proto.pathloss = pathloss.pathloss

            for component_name in pathloss.component_names:
                pathloss_proto.component_names.append(component_name)

            for remote_component_name in pathloss.remote_component_names:
                pathloss_proto.remote_component_names.append(remote_component_name)

        for antenna_pointing in self._antenna_pointings:
            antenna_pointing_proto = initial_condition_proto.antenna_pointings.add()

            for component_name in antenna_pointing.component_names:
                antenna_pointing_proto.component_names.append(component_name)

            antenna_pointing_proto.azimuth = antenna_pointing.azimuth
            antenna_pointing_proto.elevation = antenna_pointing.elevation


    def lines(self, depth=0):
        indent = ' ' * (depth * 4)

        lines = []

        lines.append('----')
        lines.append(f'name: {self.platform_name}')
        lines.append('----')

        for pointing in self._antenna_pointings:
            lines.append(f'antenna:')

            lines.extend(pointing.antenna.lines(depth))
            lines.append(f'{indent}component: {pointing.component_name}')
            lines.append(f'{indent}azimuth: {pointing.azimuth}')
            lines.append(f'{indent}elevation: {pointing.elevation}')

        if self._pov:
            lines.append(f'location:')

            lines.append(f'{indent}lat: {self.pov.latitude}')
            lines.append(f'{indent}lon: {self.pov.longitude}')
            lines.append(f'{indent}alt: {self.pov.altitude}')

            lines.append(f'{indent}speed: {self.pov.speed}')
            lines.append(f'{indent}az: {self.pov.azimuth}')
            lines.append(f'{indent}el: {self.pov.elevation}')

            lines.append(f'{indent}pitch: {self.pov.pitch}')
            lines.append(f'{indent}roll: {self.pov.roll}')
            lines.append(f'{indent}yaw: {self.pov.yaw}')

        if self._pathlosses:
            lines.append(f'pathlosses:')

            for pathloss in self._pathlosses:
                lines.append(f'{indent}{pathloss.remote_platform}: {pathloss.pathloss}')

        return lines


    def __str__(self):
        s = ''

        for line in self.lines(1):
            s += f'{line}\n'

        return s
