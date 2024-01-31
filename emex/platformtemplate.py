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

from collections import namedtuple


ComponentDescriptor = \
    namedtuple('ComponentDescriptor',
               ['name',
                'emex_type',
                'emane_node',
                'traffic_endpoint',
                'testpoint_publisher'])


class PlatformTemplate:
    def __init__(self, template_yml):
        self._name = template_yml['name']

        self._description = template_yml.get('description', self._name)

        self._component_descriptors = {}

        for name, component_dict in template_yml['components'].items():
            component_type = component_dict['type']

            traffic_endpoint = component_dict['traffic_endpoint']

            testpoint_publisher = component_dict['testpoint_publisher']

            emane_node = component_type.lower() == 'waveform'

            self._component_descriptors[name] = \
                ComponentDescriptor(name,
                                    component_type,
                                    emane_node,
                                    traffic_endpoint,
                                    testpoint_publisher)


    @property
    def name(self):
        return self._name


    @property
    def description(self):
        return self._description


    @property
    def component_descriptors(self):
        return self._component_descriptors.values()


    def component_descriptor(self, name):
        return self._component_descriptors.get(name, None)


    def build_config(self, platform_yml, ymls):
        config = {}

        platform_name = platform_yml['name']

        config['name'] = platform_name

        config['template_name'] = self.name

        config['description'] = platform_yml.get('description', config['name'])

        config['components'] = {}

        for c_descriptor in self.component_descriptors:
            #(componenttype,traffic_endpoint,testpoint_publisher)
            if not c_descriptor.name in platform_yml['from']:
                raise ValueError(f'Platform Template "{self._name}" requires ' \
                                 f'parameter "{c_descriptor.name}" but is not provided by ' \
                                 f'platform  "{platform_name}". Quitting')

            component_config = {'type': c_descriptor.emex_type}

            component_yml = ymls[c_descriptor.emex_type][platform_yml['from'][c_descriptor.name]]
            component_config['name'] = c_descriptor.name
            component_config['template_name'] = self.name
            component_config['type'] = c_descriptor.emex_type
            component_config['traffic_endpoint'] = c_descriptor.traffic_endpoint
            component_config['testpoint_publisher'] = c_descriptor.testpoint_publisher
            component_config['emane_node'] = c_descriptor.emane_node
            component_config['value'] = component_yml['name']
            component_config['template'] = component_yml['template']
            component_config['description'] = component_yml['description']
            component_config['parameters'] = component_yml['parameters']

            config['components'][c_descriptor.name] = component_config

        return config
