# Copyright (c) 2022 - Adjacent Link LLC, Bridgewater, New Jersey
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
from collections import defaultdict


class Waveform:
    @staticmethod
    def from_protobuf(builder, waveform_proto):
        # message Waveform
        # {
        #   required string type = 1;
        #   repeated ParamGroup param_groups = 2;
        #   repeated InitialCondition initial = 3;
        # }
        waveformtype = builder.waveformtypes.get(waveform_proto.type, None)

        user_config = defaultdict(lambda: {})

        for param_group in waveform_proto.param_groups:
            for param in param_group.params:
                user_config[param_group.group][param.name] = []

                for value in param.value:
                    user_config[param_group.group][param.name].append(value)

        return Waveform(waveformtype, user_config)


    def __init__(self, waveformtype, user_config={}):
        self._type = waveformtype.name

        self._parameters = waveformtype.parameters

        self._user_config = user_config

        self._raise_unset_params()


    @property
    def type(self):
        return self._type


    @property
    def parameters(self):
        return self._parameters


    @property
    def user_config(self):
        return copy.deepcopy(self._user_config)


    def to_protobuf(self, waveform_proto):
        waveform_proto.type = self.type

        for group_name, param_group in self.user_config.items():
            param_group_proto = waveform_proto.param_groups.add()

            param_group_proto.group = group_name

            for param_name, values in param_group.items():
                param = param_group_proto.params.add()

                param.name = param_name

                for value in values:
                    param.value.append(value)


    def _raise_unset_params(self):
        for group_name, param_group in self.parameters.items():
            for name, param in param_group.params.items():
                valuelist = param.default

                if not valuelist:
                    uservalue = self.user_config.get(group_name, {}).get(name, [])

                    if not uservalue:
                        raise ValueError(f'Error: {group_name} "{name}" parameter value '
                                         f'is required for waveform type "{self.type}" '
                                         f'but not set.')


    def __str__(self):
        s = f'    type: {self.type}\n'

        s+= f'    parameters:\n'

        for group_name, param_group in self.parameters.items():
            s += f'        {group_name}:\n'

            for param_name, param in param_group.params.items():
                values = param.default

                value_str = ",".join(map(str, values))

                user_values = self.user_config.get(group_name, {}).get(param_name, [])

                if user_values:
                    value_str = f'{",".join(user_values)}*'

                s += f'            {param_name}: {value_str}\n'

        return s
