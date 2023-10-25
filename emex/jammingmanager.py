# Copyright (c) 2023 - Adjacent Link LLC, Bridgewater, New Jersey
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

import logging
import shlex
import subprocess

from emex.emoemessages import JamOnEvent


class JammingManager:
    def __init__(self, nemid_map, antenna_profileid_map):
        self._nemid_map = nemid_map

        self._antenna_profileid_map = antenna_profileid_map


    def send_events(self, events):
        for evt in events:
            if isinstance(evt, JamOnEvent):
                self._jam_on(evt)
            else:
                self._jam_off(evt)

        return True,''


    def _jam_on(self, evt):
        # if the event doesn't specify any platform components, then
        # send jamming on to all of them
        all_components = not len(evt.component_names)

        for (plt_name,cmp_name),nemid in self._nemid_map.items():
            # ignore other platforms
            if not plt_name == evt.platform_name:
                continue

            # ignore components that aren't targetted
            if not all_components and not cmp_name in evt.component_names:
                continue

            # execute emane-jammer-simple-control with correct command line
            frequencies = ' '.join(map(str, evt.frequencies))

            command = \
                f'emane-jammer-simple-control {plt_name}-{cmp_name}:45715 on ' \
                f'-p {evt.txpower} ' \
                f'-b {evt.bandwidth} ' \
                f'-t {evt.period} ' \
                f'-d {evt.duty_cycle} ' \
                f'{nemid} ' \
                f'{frequencies}'

            logging.debug(f'JammingManager run "{command}"')

            subprocess.Popen(shlex.split(command),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT,
                             shell=False)


    def _jam_off(self, evt):
        # if the event doesn't specify any platform components, then
        # send jamming off to all of them
        all_components = not len(evt.component_names)

        for (plt_name,cmp_name) in self._nemid_map:
            # ignore other platforms
            if not plt_name == evt.platform_name:
                continue

            # ignore components that aren't targetted
            if not all_components and not cmp_name in evt.component_names:
                continue

            command = f'emane-jammer-simple-control {plt_name}-{cmp_name}:45715 off'

            logging.debug(f'JammingManager run "{command}"')

            subprocess.Popen(shlex.split(command),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT,
                             shell=False)
