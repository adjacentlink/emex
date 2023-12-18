# Copyright (c) 2022,2023 - Adjacent Link LLC, Bridgewater, New Jersey
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
from emex.paramtype import ParamType
from emex.utils import line_breaker


class AntennaType:
    @staticmethod
    def from_protobuf(antennatype_proto):
        # required string name = 1;
        # repeated ParamType param_types = 2;
        # optional string description = 3;
        name = antennatype_proto.name

        config_dict = {
            'name': name,
            'description': antennatype_proto.description
        }

        parameters = {}

        for param_type_proto in antennatype_proto.param_types:
            parameters.update(ParamType.configdict_from_protobuf(param_type_proto))

        config_dict['parameters'] = parameters

        return AntennaType(config_dict)


    def __init__(self, config_dict):
        self._name = config_dict['name']

        self._description = config_dict.get('description', '')

        self._paramtypes = {}

        if config_dict.get('parameters', None):
            self._paramtypes = {name: ParamType(name, values)
                                for name,values in config_dict['parameters'].items()}


    @property
    def name(self):
        return self._name


    @property
    def description(self):
        return self._description


    @property
    def paramtypes(self):
        return copy.copy(self._paramtypes)


    def to_protobuf(self, antennatype_proto):
        antennatype_proto.name = self.name

        antennatype_proto.description = self.description

        for paramtype in self._paramtypes.values():
            paramtype_proto = antennatype_proto.param_types.add()

            paramtype.to_protobuf(paramtype_proto)


    def lines(self, depth=0):
        indent = ' ' * (depth * 4)
        indent2 = ' ' * ((depth+1) * 4)

        lines = []

        lines.append(f'{indent}name: {self._name}:')

        lines.append(f'{indent}description:')

        for line in line_breaker(self.description, 60):
            lines.append(f'{indent2}{line}')

        lines.append(f'{indent}parameters:')

        for _, paramtype in self._paramtypes.items():
            lines.extend(paramtype.lines(depth+1))

        return lines

    def __str__(self):
        s = ''

        lines = self.lines(0)

        for line in lines:
            s += f'{line}\n'

        return s
