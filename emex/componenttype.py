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
from emex.paramgrouptype import ParamGroupType


class ComponentType:
    @staticmethod
    def configdict_from_protobuf(componenttype_proto):
        name = componenttype_proto.name

        componenttype_dict = {
            'name': name,
            'type': componenttype_proto.component_type,
            'value': componenttype_proto.value
        }

        parameters = {}
        for pi_group_proto in componenttype_proto.paramgroup_types:
            parameters.update(ParamGroupType.configdict_from_protobuf(pi_group_proto))

        componenttype_dict['parameters'] = parameters

        return componenttype_dict


    def __init__(self, name, componenttype_dict):
        self._name = componenttype_dict['name']

        self._emex_type = componenttype_dict['type']

        self._value = componenttype_dict['value']

        self._paramgroup_types = {
            group: ParamGroupType(group, config_dict)
            for group, config_dict in componenttype_dict['parameters'].items()
        }


    @property
    def name(self):
        return self._name


    @property
    def emex_type(self):
        return self._emex_type


    @property
    def value(self):
        return self._value


    @property
    def default_config(self):
        return { pgt.group: pgt.default_config
                 for pgt in self._paramgroup_types.values() }


    @property
    def description(self):
        return self._componenttype_type.get('description', '')


    @property
    def componenttype_type(self):
        return self._componenttype_dict['type']


    @property
    def paramgroup_types(self):
        return copy.deepcopy(self._paramgroup_types)


    def to_protobuf(self, componenttype_proto):
        componenttype_proto.name = self.name

        componenttype_proto.component_type = self.emex_type

        componenttype_proto.value = self.value

        for group_name, paramtype in self.paramgroup_types.items():
            paramtype_group_proto = componenttype_proto.paramgroup_types.add()

            paramtype.to_protobuf(paramtype_group_proto)


    def lines(self, depth=0):
        indent = ' ' * (depth * 4)

        lines = []

        lines.append(f'{indent}name: {self.name}')

        lines.append(f'{indent}type: {self.emex_type}')

        lines.append(f'{indent}value: {self.value}')

        lines.append(f'{indent}parameters:')

        for paramgroup_type in self._paramgroup_types.values():
            lines.extend(paramgroup_type.lines(depth+1))

        return lines
