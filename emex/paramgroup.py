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


class ParamGroup:
    """
    message ParamGroup
    {
      message ParamValue
      {
        required string name = 1;
        repeated string value = 2;
      }

      required string group = 1;
      repeated ParamValue params = 2;
    }
    """
    @staticmethod
    def configdict_from_protobuf(paramgroup_proto):
        param_dict = { paramgroup_proto.group: {} }

        for param_proto in paramgroup_proto.params:
            param_dict.extend({Param.configdict_from_protobuf(param_proto)})

        return param_dict


    def __init__(self, group, paramgroup_dict):
        self._group = group

        self._params = {name: Param(name, value)
                        for name, value in paramgroup_dict.items()}


    @property
    def group(self):
        return self._group


    @property
    def params(self):
        return copy.deepcopy(self._params)


    @property
    def configured(self):
        return all([p.configured
                    for p in self._params.values()])


    def unconfigured(self):
        return [(self.group, p.name)
                for p in self._params.values()
                if not p.configured]


    def get_params(self):
        tuples = []

        for p in self._params.values():
            tuples.append((self.group, p.name, p.value))

        return tuples


    def has_param(self, p_name):
        return not self._params.get(p_name, None) is None


    def get_param(self, p_name):
        param = self._params.get(p_name, None)

        if not param:
            raise ValueError(
                f'No parameter "{p_name}" in parameter group "{self.group}".')

        return param


    def set_param(self, p_name, value_list):
        param = self._params.get(p_name, None)

        if not param:
            raise ValueError(
                f'No parameter "{p_name}" in parameter group "{self.group}".')

        param.set_param(value_list)


    def to_protobuf(self, paramgroup_proto):
        paramgroup_proto.group = self.group

        for param in self._params.values():
            param_proto = paramgroup_proto.params.add()

            param.to_protobuf(param_proto)


    def lines(self, depth=0):
        indent = ' ' * (depth * 4)

        lines = []

        lines.append(f'{indent}{self._group}:')

        for _, param in self._params.items():
            lines.extend(param.lines(depth+1))

        return lines

