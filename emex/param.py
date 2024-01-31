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

from emex.utils import configstrtoval


class Param:
    @staticmethod
    def configdict_from_protobuf(param_proto):
        param_dict = {
            param_proto.name: {
                'value': [ configstrtoval(value) for value in param_proto.value ],
            }
        }

        return param_dict


    def __init__(self, name, value):
        if '.' in name:
            raise ValueError(f'Illegal character "." in {name}. Quitting.')

        self._name = name

        self._value = self._convert(value)


    def _convert(self, value):
        """
        Make sure value is a list and of the narrowest type of float,
        int, bool or string.
        """
        if not isinstance(value, list):
            return [configstrtoval(value)]
        else:
            return list(map(configstrtoval, value))


    @property
    def name(self):
        return self._name


    @property
    def value(self):
        return self._value


    @property
    def configured(self):
        """
        """
        return len(self._value) > 0


    def set_param(self, value_list):
        self._value = self._convert(value_list)


    def to_protobuf(self, param_proto):
        param_proto.name = self.name

        for value in self._value:
            param_proto.value.append(str(value))


    def lines(self, depth=0):
        indent = ' ' * (depth * 4)

        value = ''

        if self._value:
            value = ','.join(map(str, self.value))

        return [f'{indent}{self.name}: [{value}]']
