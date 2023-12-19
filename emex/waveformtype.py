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
from emex.utils import line_breaker
from emex.paramgrouptype import ParamGroupType


class WaveformType:
    @staticmethod
    def from_protobuf(waveformtype_proto):
        config_dict = {}

        config_dict['name'] = waveformtype_proto.name

        config_dict['template'] = waveformtype_proto.template

        config_dict['description'] = waveformtype_proto.description

        params = {}

        for paramgroup_type in waveformtype_proto.paramgroup_types:
            group_params = {}

            for paramtype in paramgroup_type.param_types:
                param_name = paramtype.name

                value_default = []

                for default_value in paramtype.default:
                    value_default.append(default_value)

                group_params[param_name] = {'default': value_default}

            params[paramgroup_type.name] = group_params

        config_dict['parameters'] = params

        return WaveformType(config_dict)


    def __init__(self, config_dict):
        self._name = config_dict['name']

        self._template = config_dict['template']

        self._description = config_dict.get('description', self.name)

        self._parameters = { name:ParamGroupType(name, values)
                             for name, values in config_dict.get('parameters', {}).items() }


    @property
    def name(self):
        return self._name


    @property
    def template(self):
        return self._template


    @property
    def description(self):
        return self._description


    @property
    def parameters(self):
        return copy.deepcopy(self._parameters)


    def to_protobuf(self, waveformtype_proto):
        waveformtype_proto.name = self.name

        waveformtype_proto.description = self.description

        waveformtype_proto.template = self.template

        for group_name, param_group in self.parameters.items():
            paramgroup_type_proto = waveformtype_proto.paramgroup_types.add()

            paramgroup_type_proto.name = group_name

            for param_name, paramtype in param_group.paramtypes.items():
                paramtype_proto = paramgroup_type_proto.param_types.add()

                paramtype_proto.name = param_name

                if paramtype:
                    param_default = paramtype.default

                    if not isinstance(param_default, list):
                        param_default = [param_default]

                    for default_value in param_default:
                        paramtype_proto.default.append(str(default_value))


    def __str__(self):
        s = f'name: {self.name}\n'

        s+= f'template: {self.template}\n'

        s+= f'description:\n'
        for line in line_breaker(self.description, 60):
            s+= f'    {line}\n'

        s+= f'parameters:\n'

        for _, param_group in self.parameters.items():
            for line in str(param_group).strip().split('\n'):
                s+= f'    {line}\n'

        return s
