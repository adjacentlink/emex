# Copyright (c) 2022,2023 - Adjacent Link LLC, Bridgewater, New Jersey
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
import os
import socket
import struct
import sys
import time

from emex.emexdrpcclient import EmexdRpcClient
from emex.scenariorpcclient import ScenarioRpcClient
from emex.emoestate import EmoeState
from emex.emoe import Emoe
from emex.emoeerror import EmoeError
from emex.eventsequencer import EventSequencer
from emex.utils import load_monitor


class ScenarioRunner():
    def __init__(self, emexd_endpoint, emoe_name, scenario_builder, output_path=None, monitor=False):
        self._emexd_endpoint = emexd_endpoint

        self._emexd = EmexdRpcClient(self._emexd_endpoint)

        self._antennatypes, self._platformtypes = self._emexd.getmodels()

        self._emoe_name = emoe_name

        self._scenario_builder = scenario_builder

        self._output_path = output_path

        self._emoe = self._build_emoe(emoe_name, scenario_builder)

        self._monitor = load_monitor('emex')(self._emoe) if monitor else None

        self._total_cpus = self._emexd.listemoes().total_cpus


    def _build_emoe(self, emoe_name, scenario_builder):
        # create emoe from scenario
        """
        emoe:
            platforms:
                lteue-001:
                    type: scr_lte.ue
                    parameters:
                        r1.rm.resourceblocktxpower: 24.0
                lteue-002:
                    type: scr_lte.ue
                    parameters:
                        r1.rm.resourceblocktxpower: 24.0
                lteenb-001:
                    type: bs_lte.enb
                    parameters:
                        r1.rm.resourceblocktxpower: 24.0
                lteepc-001:
                    type: h_lte.epc
        initial_conditions:
            pov: |
                lteue-001  41.112998 -111.983357 5.0
                lteue-00   41.102036 -111.968208 5.0
                lteenb-004 41.111182 -111.951816 100.0

        """
        platforms,antennas,initial_conditions = \
            self._scenario_builder.build(self._platformtypes, self._antennatypes)

        emoe = Emoe(emoe_name,
                    platforms=platforms,
                    antennas=antennas,
                    initial_conditions=initial_conditions)

        logging.debug(emoe)

        return emoe


    def required_cpus(self):
        return self._emoe.cpus


    def total_cpus(self):
        return self._total_cpus


    def available_cpus(self):
        return self._emexd.listemoes().available_cpus


    def check(self):
        # And send it to the server to check
        reply = self._emexd.checkemoe(self._emoe)

        return reply.result,reply.message


    def start_emoe(self):
        # If the check passes, start it
        reply = self._emexd.startemoe(self._emoe)

        if not reply.result:
            raise EmoeError(
                f'{reply.emoe_name} start failed with message "{reply.message}".')

        logging.info(
            f'{reply.emoe_name} successfully started with message '
            f'"{reply.message}".')


    def wait_for_emoe_running(self):
        sys.stdout.write(f'Waiting for {self._emoe.name} state RUNNING ')

        emoe_running = False
        emoe_stopped = False
        emoe_entry = None
        found = True
        i = 1

        while found and not emoe_running and not emoe_stopped:
            reply = self._emexd.listemoes()

            found = False

            for entry in reply.emoe_entries:
                if not entry.emoe_name == self._emoe.name:
                    continue

                found = True

                emoe_entry = entry
                if entry.state == EmoeState.RUNNING:
                    emoe_running = True
                    break
                elif entry.state >= EmoeState.STOPPING:
                    emoe_stopped = True
                    break
            time.sleep(1)
            sys.stdout.write(f'\33[2K\r %02d {self._emoe.name} state: {entry.state.name}' % i)
            i+=1
            sys.stdout.flush()

        sys.stdout.write('\n')
        return emoe_entry


    def get_endpoints(self, emoe_entry):
        otestpoint_publish_endpoint = None
        emoe_endpoint = None

        print('###############')
        print(f'handle: {emoe_entry.handle}')
        print(f'name: {emoe_entry.emoe_name}')
        print(f'state: {emoe_entry.state.name}')
        print(f'cpus: {emoe_entry.cpus}')
        print(f'accesors:')
        for accessor in emoe_entry.service_accessors:
            print(f'   {accessor.name}: {accessor.ip_address}:{accessor.port}')
            if accessor.name == 'emexcontainerd':
                emoe_endpoint = (accessor.ip_address, accessor.port)
            elif accessor.name == 'otestpoint-publish':
                otestpoint_publish_endpoint = (accessor.ip_address, accessor.port)
        print('###############')

        return otestpoint_publish_endpoint,emoe_endpoint


    def start_monitor(self,
                       emoe_entry,
                       otestpoint_publish_endpoint):
        if not self._monitor:
            return

        # invoke data recorder
        if not self._output_path:
            self._output_path = f'{emoe_entry.handle}-{self._emoe.name}'

        if os.path.exists(self._output_path):
            logging.error(f'{self._output_path} already exists')
        os.makedirs(self._output_path)

        self._monitor.run(self._output_path, otestpoint_publish_endpoint)


    def run_scenario(self, emoe_endpoint):
        # issue events
        scenario_rpc = ScenarioRpcClient(emoe_endpoint)

        logging.info(f'run {self._scenario_builder.name}')

        # send a StartFlowsRequest for all flows
        sequencer = EventSequencer(self._scenario_builder.events)

        ok = False,
        message = None
        flows_df = None

        for eventtime,eventdict in sequencer:
            logging.info(f'event time=%0.1f' % eventtime)

            ok,message,flows_df = scenario_rpc.send_event(eventdict)

        return flows_df


    def stop_monitor(self, flows_df):
        if self._monitor:
            self._monitor.stop(flows_df=flows_df)

            logging.info(f'Output data written to {self._output_path}')


    def stop_emoe(self, emoe_handle):
        # stop emoe
        logging.info('scenario complete, stop emoe')
        reply = self._emexd.stopemoe(emoe_handle)

        if not reply.result:
            raise EmoeError(
                f'{reply.emoe_name} stop failed with message "{reply.message}".')

        logging.info(f'{reply.emoe_name} stopped.')


    def run(self):
        check_reply,check_message = self.check()

        if not check_reply:
            logging.error('failed check_reply with {check_message}')

            return check_reply,check_message

        self.start_emoe()

        emoe_entry = self.wait_for_emoe_running()

        if emoe_entry.state >= EmoeState.STOPPING:
            raise EmoeError(f'{emoe_entry.emoe_name} failed to start.')

        otestpoint_publish_endpoint,emoe_endpoint = self.get_endpoints(emoe_entry)

        self.start_monitor(emoe_entry, otestpoint_publish_endpoint)

        flows_df = self.run_scenario(emoe_endpoint)

        self.stop_monitor(flows_df)

        self.stop_emoe(emoe_entry.handle)
