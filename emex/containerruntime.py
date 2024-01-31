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
import logging

from collections import namedtuple


HostDevice = namedtuple(
    'RadioDevice', ['name','ipv4address','masklen']
)


RadioDevice = namedtuple(
    'RadioDevice', ['name','ipv4address','masklen','nemid']
)


BridgeDevice = namedtuple(
    'BridgeDevice', ['name','ipv4address','masklen','macaddress']
)


class ContainerRuntime:
    """Information about each container in the emulation.

    Centralize attributes about each container in the emulation - control
    and radio endpoint information and attributes of the contained
    component - whether this container is a traffic source/sink or
    exposes testpoint information.
    """
    def __init__(self, hostname, component_descriptor):
        self._hostname = hostname

        self._component_descriptor = component_descriptor

        self._device_map = {}


    @property
    def hostname(self):
        return copy.copy(self._hostname)


    @property
    def traffic_endpoint(self):
        return self._component_descriptor.traffic_endpoint


    @property
    def testpoint_publisher(self):
        return self._component_descriptor.testpoint_publisher


    @property
    def emane_node(self):
        return self._component_descriptor.emane_node


    @property
    def component_descriptor(self):
        return self._component_descriptor


    def get_device(self, device_name):
        return self._device_map.get(device_name, None)


    def add_device(self, device_name, device):
        logging.debug(f'add_device: {self.hostname} {device_name} {device.ipv4address}')

        self._device_map[device_name] = device


    @property
    def device_map(self):
        return self._device_map


    def devices(self):
        return self._device_map.values()


    def radio_devices(self):
        return [device
                for device in self._device_map.values()
                if isinstance(device, RadioDevice)]


    def host_devices(self):
        return [device
                for device in self._device_map.values()
                if isinstance(device, HostDevice)]


    def device(self, device_name):
        return self._device_map.get(device_name, None)
