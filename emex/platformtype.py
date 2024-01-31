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
import os
from yaml import safe_load

from emex.componenttype import ComponentType
from emex.component import Component
from emex.utils import line_breaker


class PlatformType:
    @staticmethod
    def from_protobuf(platformtype_proto):
        config_dict = {}

        config_dict['name'] = platformtype_proto.name

        config_dict['description'] = platformtype_proto.description

        config_dict['template_name'] = platformtype_proto.template_name

        componenttype_dict = {}

        for ct_proto in platformtype_proto.componenttypes:
            componenttype_dict.update({
                ct_proto.component_type: ComponentType.configdict_from_protobuf(ct_proto)
            })

        config_dict['components'] = componenttype_dict

        return PlatformType(config_dict)


    def __init__(self, config_dict):
        self._name = config_dict['name']

        self._description = config_dict.get('description', self.name)

        self._template_name = config_dict['template_name']

        self._componenttypes = {}

        for name, componenttype_dict in config_dict.get('components', {}).items():
            self._componenttypes[name] = ComponentType(name, componenttype_dict)


    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, val):
        self._name = val

    @property
    def emex_type(self):
        return 'platformtype'


    @property
    def template_name(self):
        return self._template_name


    @property
    def description(self):
        return self._description


    @property
    def componenttypes(self):
        return copy.deepcopy(self._componenttypes)


    def to_protobuf(self, platformtype_proto):
        platformtype_proto.name = self.name

        platformtype_proto.description = self.description

        platformtype_proto.template_name = self.template_name

        for _, componenttype in self._componenttypes.items():
            componenttype_proto = platformtype_proto.componenttypes.add()

            componenttype.to_protobuf(componenttype_proto)


    def configure_components(self, user_config, labels={}):
        """
        Create a component for each componenttype and with
        and user_config values overriding defaults.
        """
        components = []

        for ct in self._componenttypes.values():
            component_config = ct.default_config

            user_component_config = user_config.get(ct.name, {})

            for pg_name, params in user_component_config.items():
                for p_name, p_value in params.items():
                    component_config[pg_name][p_name] = p_value

            component_dict = {
                'name': ct.name,
                'type': ct.emex_type,
                'value': ct.value,
                'parameters': component_config,
                'labels': labels.get(ct.name,[])
            }

            components.append(Component(ct.name, component_dict))

        return components


    def __str__(self):
        s = f'name: {self.name}\n'
        s+= f'template: {self.template_name}\n'
        s+= f'description:\n'

        for line in line_breaker(self.description, 60):
            s+= f'    {line}\n'

        s+= f'components:\n'

        lines = []

        for ct in self._componenttypes.values():
            lines.extend(ct.lines(1))

        for line in lines:
            s += f'{line}\n'

        return s
