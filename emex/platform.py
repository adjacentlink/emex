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

from collections import defaultdict
import copy
from fractions import Fraction
import logging

from emex.types import platformtemplates


class Platform:
    @staticmethod
    def from_protobuf(platform_proto, platformtypes):
        platformtype = platformtypes.get(platform_proto.platformtype, None)

        if not platformtype:
            raise ValueError(f'"{platform_proto.platformtype}" not recognized. Ignoring.')

        user_config = {}

        labels = defaultdict(lambda: [])

        for component_proto in platform_proto.components:
            user_config[component_proto.name] = {}

            for label in component_proto.labels:
                labels[component_proto.name].append(label)

            for param_group_proto in component_proto.param_groups:
                group_params = {}

                for param_proto in param_group_proto.params:
                    p_name = param_proto.name

                    p_values = list(param_proto.value)

                    group_params[p_name] = p_values

                user_config[component_proto.name][param_group_proto.group] = \
                    group_params

        return Platform(platform_proto.name, platformtype, user_config, labels)


    def __init__(self, name, platformtype, user_config={}, labels={}):
        # Preconditions
        # 1. Combination of platformtype default values with user_config
        #    overlay covers all assignale parameters.
        self._name = name

        self._platformtype = platformtype

        self._components = {
            c.name: c
            for c in self._platformtype.configure_components(user_config, labels)
        }


    def __lt__(self, other):
        return self.name < other.name


    @property
    def name(self):
        return self._name


    @property
    def platformtype(self):
        return copy.deepcopy(self._platformtype)


    @property
    def platformtype_name(self):
        return self._platformtype.name


    @property
    def nemids(self):
        nemids = []

        for _,c in self._components.items():
            if c.nemid:
                nemids.extend(c.nemid.value)
            else:
                logging.warning(f'platform component "{self.name}.{c.name}" '
                                f'does not contain an emane nemid parameter. '
                                f'This warning may be due to trying to assign an initial '
                                f'condition (pov, pathloss) to a non-emane platform '
                                f'component. Ignoring.')

        return nemids


    def resources(self):
        resources = defaultdict(lambda: 0)

        for c, pg_name, p_name, value_list in self.get_params():
            if not pg_name == 'resources':
                continue

            resources[p_name] += sum(map(Fraction, value_list))

        return resources


    @property
    def cpus(self):
        return self.resources()['cpus']


    @property
    def components(self):
        return self._components.values()


    @property
    def component_names(self):
        return sorted(self._components.keys())


    def component_by_name(self, name):
        return self._components.get(name, None)


    def has_component(self, name):
        return name in [c.name for c in self._components.values()]


    @property
    def configured(self):
        return all([c.configured for c in self._components.values()])


    def unconfigured(self):
        unconfigured = []

        for c in self._components.values():
            unconfigured.extend(c.unconfigured())

        return unconfigured


    def labels(self):
        labels = {}

        for c_name, c in self._components:
            labels[c_name] = c.labels

        return labels


    def add_label(self, c_name, label):
        component = self._components.get(c_name, None)

        if not component:
            raise ValueError(f'No component "{c_name}" in platform "{self.name}".')

        component.add_label(label)


    def get_params(self):
        tuples = []

        for c in self._components.values():
            tuples.extend(c.get_params())

        return tuples


    def get_param(self, c_name, pg_name, p_name):
        component = self._components.get(c_name, None)

        if not component:
            raise ValueError(f'No component "{c_name}" in platform "{self.name}".')

        return component.get_param(pg_name, p_name)


    def set_param(self, c_name, pg_name, p_name, value_list):
        component = self._components.get(c_name, None)

        if not component:
            raise ValueError(f'No component "{c_name}" in platform "{self.name}".')

        component.set_param(pg_name, p_name, value_list)


    def get_component_descriptor(self, component_name):
        template = platformtemplates()[self.platformtype.template_name]

        return template.component_descriptor(component_name)


    def to_protobuf(self, platform_proto):
        platform_proto.name = self._name

        platform_proto.platformtype = self.platformtype.name

        for component in self._components.values():
            component_proto = platform_proto.components.add()

            component.to_protobuf(component_proto)


    def __str__(self):
        s = '----\n'
        s += f'name: {self.name}\n'
        s += '----\n'

        s+= f'type: {self.platformtype_name}\n'

        s+= f'components:\n'

        lines = []

        for c in self._components.values():
            lines.extend(c.lines(1))

        for line in lines:
            s += f'{line}\n'

        return s
