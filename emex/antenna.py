# Copyright (c) 2022 - Adjacent Link LLC, Bridgewater, New Jersey
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

import copy
from emex.param import Param
from emex.types import antennatypes


class Antenna:
    @staticmethod
    def from_protobuf(antenna_proto, antennatypes=antennatypes()):
        # required string name = 1;
        # required string antenna_type = 1;
        # repeated ParamValue params = 2;

        antennatype = antennatypes.get(antenna_proto.antenna_type, None)

        if not antennatype:
            raise ValueError(f'"{antenna_proto.antenna_type}" not recognized. Ignoring.')

        name = antenna_proto.name

        config_dict = {}

        for paramvalue_proto in antenna_proto.params:
            config_dict[paramvalue_proto.name] = \
                list(paramvalue_proto.value)

        return Antenna(name, antennatype, config_dict)


    def __init__(self, name, antennatype, config_dict={}):
        self._name = name

        self._antennatype_name = antennatype.name

        self._params = {}

        for name, paramtype in antennatype.paramtypes.items():
            self._params[name] = Param(name, paramtype.default)

        for name, value in config_dict.items():
            if not name in self._params:
                raise ValueError(f'Unknown antenna parameter "{name}".')

            self._params[name] = Param(name, value)


    @property
    def name(self):
        return self._name


    @property
    def antennatype_name(self):
        return self._antennatype_name


    @property
    def params(self):
        return copy.copy(self._params)


    @property
    def north(self):
        return self._params['north'].value[0]


    @property
    def east(self):
        return self._params['east'].value[0]


    @property
    def up(self):
        return self._params['up'].value[0]


    def to_protobuf(self, antenna_proto):
        antenna_proto.name = self.name

        antenna_proto.antenna_type = self._antennatype_name

        for param in self._params.values():
            param_proto = antenna_proto.params.add()

            param.to_protobuf(param_proto)


    def lines(self, depth=0):
        indent = ' ' * (depth * 4)

        lines = []

        lines.append(f'----')
        lines.append(f'{indent}name: {self._name}')
        lines.append(f'{indent}----')

        lines.append(f'{indent}parameters:')

        for _, param in self._params.items():
            lines.extend(param.lines(depth+1))

        return lines


    def __str__(self):
        s = ''

        lines = self.lines(0)

        for line in lines:
            s += f'{line}\n'

        return s
