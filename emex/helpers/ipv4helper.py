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

from emex.confighelper import ConfigHelper
from emex.utils import group_components_by_label


class Ipv4Helper(ConfigHelper):
    """
    Ipv4Helper assigns a unique Ipv4 address to each network
    interface.

    It then checks that all NEMs are assigned a unique
    nemid and raises an exception.
    """
    def __init__(self, subnet_format='10.0.%d.%d', subnet_start=1):
        self._subnet_format = subnet_format

        self._subnet_start = subnet_start


    def configure(self, platforms):
        wf_groups = group_components_by_label(platforms, label='net')

        # assign ip addresses by wf group
        for subnetid,((wft,nl),group_tuples) in enumerate(wf_groups.items(), start=1):
            # first check if there are configured and unconfigured addresses in
            # one group. don't handle that case - all or none.
            configured = []

            unconfigured = []

            for platform,component in group_tuples:
                descriptor = platform.get_component_descriptor(component.name)

                if not descriptor.traffic_endpoint:
                    continue

                address = component.get_param('net', 'ipv4address')

                if address.value:
                    configured.append(component)
                else:
                    unconfigured.append(component)

            if configured and unconfigured:
                netlist = ', '.join(list(nl))

                raise ValueError(f'Waveform "{wft}" net labels "{netlist}" ' \
                                 f'has configured and unconfigured ipv4_address ' \
                                 f'values and cannot be automatically configured.')

            if not unconfigured:
                continue

            for hostid,component \
                in enumerate(unconfigured, start=self._subnet_start):

                component.set_param('net',
                                    'ipv4address',
                                    self._subnet_format % (subnetid, hostid))


    def check(self, platforms):
        for platform in platforms:
            for c_name,pg_name,p_name,value in platform.get_params():
                if pg_name == 'net' and p_name == 'ipv4address':
                    if not value:
                        raise ValueError(f'net.ipv4address is not set for {platform.name}.{c.name}')
