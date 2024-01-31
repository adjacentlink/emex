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
from emex.paramtype import ParamType


class ParamGroupType:
    @staticmethod
    def configdict_from_protobuf(paramgrouptype_proto):
        parameters  = {}

        for paramtype_proto in paramgrouptype_proto.param_types:
            parameters.update(ParamType.configdict_from_protobuf(paramtype_proto))

        return { paramgrouptype_proto.name: parameters }


    def __init__(self, group, config_dict):
        if '.' in group:
            raise ValueError(f'Illegal character "." in {group}. Quitting.')

        self._group = group

        self._paramtypes = { name: ParamType(name, values)
                             for name, values in config_dict.items() }


    @property
    def group(self):
        return self._group


    @property
    def paramtypes(self):
        return copy.copy(self._paramtypes)


    @property
    def default_config(self):
        return { param.name: param.default
                 for param in self._paramtypes.values() }


    def to_protobuf(self, paramgrouptype_proto):
        paramgrouptype_proto.name = self.group

        for _, paramtype in self.paramtypes.items():
            paramtype_proto = paramgrouptype_proto.param_types.add()

            paramtype.to_protobuf(paramtype_proto)


    def lines(self, depth=0):
        indent = ' ' * (depth * 4)

        lines = []

        lines.append(f'{indent}{self._group}:')

        for _, paramtype in self._paramtypes.items():
            lines.extend(paramtype.lines(depth+1))

        return lines
