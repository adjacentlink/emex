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

from collections import defaultdict
import logging

from emex.platformtemplate import ComponentDescriptor
from emex.emoestate import EmoeState
from emex.containerruntime import ContainerRuntime,HostDevice,RadioDevice


class EmoeRuntime:
    """
    Contains all of the Emoe runtime configured information
    required to interact with the running Emoe - especially
    nemids, interface addresses and port numbers.

    It is organized hierarchichally by container name and
    the endpoints each has.
    """
    def __init__(self, timestamp, client_id, emoe, cpus, config):
        self._state = EmoeState.QUEUED

        # track whether this EMOE ever reached the running statue
        self._did_run = False

        self._container = None

        self._container_name = None

        self._container_id = None

        self._timestamp = timestamp

        self._client_id = client_id

        self._start_attempts = 3

        self._stop_count = 0

        self._emoe = emoe

        self._cpus = cpus

        self._config = config

        self._container_runtimes = defaultdict(lambda: {})

        self._container_ports = {}

        self._host_port_mappings = {}

        if self._config.container_datetime_tag_format == 'prefix':
            self._container_name = f'{self._timestamp.emoe_id}.{self._emoe.name}'
        elif self._config.container_datetime_tag_format == 'suffix':
            self._container_name = f'{self._emoe.name}.{self._timestamp.emoe_id}'
        else:
            self._container_name = self._emoe.name

        for plt in emoe.platforms:
            for c in plt.components:
                addr = None
                mask = None
                device_name = None
                nemid = None
                for c_name, pg_name, p_name, p_value in c.get_params():
                    if p_name == 'ipv4address':
                        addr = p_value[0]
                    elif p_name == 'ipv4mask':
                        mask = p_value[0]
                    elif p_name == 'device':
                        device_name = p_value[0]
                    elif p_name == 'nemid':
                        nemid = p_value[0]

                if addr and mask and device_name:
                    container_rt = self.get_container_runtime(plt.name, c.name)

                    if nemid:
                        container_rt.add_device(device_name,
                                                RadioDevice(device_name, addr, mask, nemid))
                    else:
                        container_rt.add_device(device_name,
                                                HostDevice(device_name, addr, mask))


    def __eq__(self, other):
        if not isinstance(other, EmoeRuntime):
            return False

        return self.emoe_id == other.emoe_id


    @property
    def timestamp(self):
        return self._timestamp.timestamp


    @property
    def emoe_id(self):
        return self._timestamp.emoe_id


    @property
    def workdir(self):
        return self._timestamp.workdir(self._emoe.name)


    def mcast_address(self):
        return self._timestamp.mcast_address


    @property
    def client_id(self):
        return self._client_id


    @property
    def container_name(self):
        if self._container and not self._container.name == self._container_name:
            logging.error(f'conflicting internal container names '
                          f'{self._container.name} and {self._container_name}')

        return self._container_name


    @property
    def container_ports(self):
        return self._container_ports


    def add_container_port(self, service_name, container_port):
        self._container_ports[service_name] = container_port


    @property
    def host_port_mappings(self):
        return self._host_port_mappings


    def add_host_port_mapping(self, host_port, service_name):
        if not service_name in self._container_ports:
            logging.error(f'Unknown service {service_name} when trying '
                          f'to map to host port {host_port}')

            return

        self._host_port_mappings[host_port] = \
            (service_name, self._container_ports[service_name])


    def clear_host_port_mappings(self):
        self._host_port_mappings.clear()


    @property
    def emoe(self):
        return self._emoe


    @property
    def cpus(self):
        return sorted(list(self._cpus))

    @property
    def num_cpus(self):
        return len(self._cpus)


    @property
    def state(self):
        return self._state


    @state.setter
    def state(self, state):
        self._state = state

        if self._state == EmoeState.RUNNING:
            self._did_run = True


    @property
    def did_connect(self):
        # a container_id is assigned if and when the
        # container connects to emexd
        return self._container_id is not None


    @property
    def did_run(self):
        return self._did_run


    @property
    def container(self):
        return self._container


    @container.setter
    def container(self, container):
        self._container = container


    @property
    def container_id(self):
        return self._container_id


    @container_id.setter
    def container_id(self, container_id):
        self._container_id = container_id


    @property
    def container_runtimes(self):
        return self._container_runtimes


    @property
    def stop_count(self):
        return self._stop_count


    @stop_count.setter
    def stop_count(self, count):
        self._stop_count = count


    def can_start(self):
        self._start_attempts = max(self._start_attempts-1, -1)

        return self._start_attempts >= 0


    def get_container_runtime(self, platform_name, component_name):
        crt = self._container_runtimes.get((platform_name, component_name), None)

        if crt:
            return crt

        platform = self.emoe.platform_by_name(platform_name)

        if platform:
            component_descriptor = platform.get_component_descriptor(component_name)

        else:
            component_descriptor = \
                ComponentDescriptor(f'{platform_name}-{component_name}',
                                    'helper',
                                    False,
                                    False,
                                    False)

        crt = ContainerRuntime(f'{platform_name}-{component_name}', component_descriptor)

        self._container_runtimes[(platform_name,component_name)] = crt

        return crt


    def control_endpoints(self):
        ces = []

        for (plt_name,c_name),cr in sorted(self._container_runtimes.items()):
            for device in cr.devices():
                if not device.name == 'backchan0':
                    continue
                ces.append((plt_name,
                            c_name,
                            device.name,
                            device.ipv4address,
                            device.masklen,
                            device.macaddress,
                            cr))

        return ces


    def radio_endpoints(self):
        res = []

        for (plt_name,c_name),cr in sorted(self._container_runtimes.items()):
            for device in cr.radio_devices():
                res.append((plt_name,
                            c_name,
                            device.name,
                            device.ipv4address,
                            device.masklen,
                            device.nemid,
                            cr))

        return res


    def port_map(self):
        """
         Collect mapping information for the container daemon to
         use to translate platform based traffic commands into
         mgen remote control commands - name mapping of platform
         names to their traffic endpoint container hostname, and
         the ipv4 address and device name that is the traffice
         endpoint - where mgen instances should listen for
         traffic or send it frome.

           platformname,hostname,ipv4address,mgen_remote_control_port
        """
        port_map_entries = []

        for (plt_name,c_name),crt in sorted(self.container_runtimes.items()):
            if not crt.traffic_endpoint:
                continue

            platform = self.emoe.platform_by_name(plt_name)

            device = platform.get_param(c_name, 'net', 'device').value[0]

            ipv4address = platform.get_param(c_name, 'net', 'ipv4address').value[0]

            port_map_entries.append((plt_name,crt.hostname,ipv4address,device))

        return port_map_entries


    def nemid_map(self):
        """
         Return a list of platform_name,component_name,nemid mapping
         values for all nemids in the network.
        """
        nemid_map_entries = {}

        for plt in self.emoe.platforms:
            for c_name, pg_name, p_name, p_value in plt.get_params():
                if not p_name == 'nemid':
                    continue

                nemid = p_value[0]

                nemid_map_entries[(plt.name,c_name)] = nemid

        return nemid_map_entries
