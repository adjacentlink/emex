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


class ParamType:
    @staticmethod
    def configdict_from_protobuf(paramtype_proto):
        type_dict = {
            paramtype_proto.name: {
                'description': paramtype_proto.name,
                'default': [ default for default in paramtype_proto.default ],
            }
        }

        return type_dict


    def __init__(self, name, type_dict):
        if '.' in name:
            raise ValueError(f'Illegal character "." in {name}. Quitting.')

        self._name = name

        self._type_dict = type_dict

        if not self._type_dict:
            self._type_dict = {}

        if not 'description' in  self._type_dict:
            self._type_dict['description'] = ''

        if not 'default' in self._type_dict:
            self._type_dict['default'] = []
        else:
            if not isinstance(self._type_dict['default'], list):
                self._type_dict['default'] = [self._type_dict['default']]

        self._type_dict['default'] = \
            list(map(configstrtoval, self._type_dict['default']))


    @property
    def name(self):
        return self._name


    @property
    def description(self):
        return self._type_dict['description']


    @property
    def default(self):
        return self._type_dict['default']


    def to_protobuf(self, paramtype_proto):
        paramtype_proto.name = self.name

        paramtype_proto.description = self.description

        for default in self.default:
            paramtype_proto.default.append(str(default))


    def lines(self, depth=0):
        indent = ' ' * (depth * 4)

        default = ','.join(list(map(str, self.default)))

        return [f'{indent}{self.name}: [{default}]']
