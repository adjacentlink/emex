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
from emex.paramgroup import ParamGroup


class Component:
    @staticmethod
    def configdict_from_protobuf(component_proto):
        name = component_proto.name

        labels = set([label for label in component_proto.labels])

        component_dict = {
            'name': name,
            'type': component_proto.component_type,
            'value': component_proto.value,
            'labels': labels
        }

        parameters = {}

        for pi_group_proto in component_proto.param_groups:
            parameters.update(ParamGroup.configdict_from_protobuf(pi_group_proto))

        component_dict['parameters'] = parameters

        return component_dict


    def __init__(self, name, component_dict):
        self._name = component_dict['name']

        self._emex_type = component_dict['type']

        self._emex_type_value = component_dict['value']

        self._param_groups = {
            group: ParamGroup(group, config_dict)
            for group, config_dict in component_dict['parameters'].items()
        }

        self._labels = component_dict['labels']


    @property
    def name(self):
        return self._name


    def __lt__(self, other):
        """
        Implement less than to allow components to be sorted
        by name.
        """
        return self.name < other.name


    @property
    def emex_type(self):
        return self._emex_type


    @property
    def emex_type_value(self):
        return self._emex_type_value


    @property
    def labels(self):
        return tuple(sorted(self._labels))


    @property
    def nemid(self):
        if not self.has_param('emane', 'nemid'):
            return []

        return self.get_param('emane', 'nemid')


    def add_label(self, label):
        self._labels.add(label)


    @property
    def param_groups(self):
        return copy.deepcopy(self._param_groups)


    @property
    def configured(self):
        return all([pg.configured for pg in self._param_groups.values()])


    def unconfigured(self):
        unconfigured = []

        for pg in self._param_groups.values():
            unconfigured.extend([(self.name, pg_name, p_name)
                                 for pg_name, p_name in pg.unconfigured()])

        return unconfigured


    def get_params(self):
        tuples = []

        for pg in self._param_groups.values():
            for pg_name, p_name, p_value in pg.get_params():
                tuples.append((self.name, pg_name, p_name, p_value))

        return tuples


    def has_param(self, pg_name, p_name):
        param_group =  self._param_groups.get(pg_name, None)

        if not param_group:
            return False

        return param_group.has_param(p_name)


    def get_param(self, pg_name, p_name):
        param_group = self._param_groups.get(pg_name, None)

        if not param_group:
            raise ValueError(
                f'No parameter group "{pg_name}" in component "{self.name}".')

        return param_group.get_param(p_name)


    def set_param(self, pg_name, p_name, value_list):
        param_group = self._param_groups.get(pg_name, None)

        if not param_group:
            raise ValueError(
                f'No parameter group "{pg_name}" in component "{self.name}".')

        param_group.set_param(p_name, value_list)


    def to_protobuf(self, component_proto):
        component_proto.name = self.name

        component_proto.component_type = self.emex_type

        component_proto.value = self.emex_type_value

        for label in self.labels:
            component_proto.labels.append(label)

        for group_name, param in self.param_groups.items():
            param_group_proto = component_proto.param_groups.add()

            param.to_protobuf(param_group_proto)


    def lines(self, depth=0):
        indent = ' ' * (depth * 4)

        label_indent = ' ' * ((depth+1) * 4)

        lines = []

        lines.append(f'{indent}name: {self.name}')

        lines.append(f'{indent}emex_type: {self.emex_type}')

        lines.append(f'{indent}emex_type_value: {self.emex_type_value}')

        lines.append(f'{indent}labels:')

        for label in self.labels:
            lines.append(f'{label_indent}{label}')

        lines.append(f'{indent}parameters:')

        for param_group in self._param_groups.values():
            lines.extend(param_group.lines(depth+1))

        return lines
