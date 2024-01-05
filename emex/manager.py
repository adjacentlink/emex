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

"""Top level manager of the EMEX server. Coordinates container
execution, resource allocation, configuration generation and EMOe
state tracking.
"""
from collections import defaultdict
import logging
from queue import Queue
import os
import shutil

from emex.builder import Builder
from emex.emoecommand import EmoeCommand
from emex.emoestate import EmoeState
from emex.emoeruntime import EmoeRuntime
from emex.containermanager import ContainerManager
from emex.resourcetracker import ResourceTracker
from emex.timestamper import Timestamper
from emex.emoe import Emoe


class Manager:
    def __init__(self, broker, config, container_worker_connect_endpoint):
        self._broker = broker

        self._config = config

        self._cpum = ResourceTracker('cpu',
                                     config.allowed_cpus_set)

        self._hpm = ResourceTracker('host port',
                                    config.allowed_host_ports_set)

        self._cm = ContainerManager(config,
                                    self,
                                    self._hpm,
                                    container_worker_connect_endpoint)

        self._builder = Builder.create()

        self._emoes_by_client_id = defaultdict(lambda: [])

        self._emoes_by_emoe_id = {}

        os.makedirs(Timestamper.EMEX_WORKDIR, exist_ok=True)

        self._timestamper = Timestamper()


    @property
    def total_cpus(self):
        return self._cpum.num_available + self._cpum.num_allocated


    @property
    def available_cpus(self):
        return self._cpum.num_available


    def reset(self):
        self._cm.stop_all_emex_containers()


    def reset_synchronous(self):
        self._cm.stop_all_emex_containers_synchronous()


    def stop_client_containers_synchronous(self):
        for emoe_rt in self._emoes_by_emoe_id.values():
            logging.info(f'stop container {container.name}')

            if emoe_rt.container and emoe_rt.container.status.lower() in ('created', 'running'):
                emoe_rt.container.stop()

                emoe_rt.container.remove(force=True)


    def reset_client(self, client_id):
        for emoe_rt in self._emoes_by_client_id[client_id]:
            self.stop_emoe(client_id, emoe_rt.emoe_id)


    def get_models(self):
        return self._builder.platformtypes,self._builder.antennatypes


    def check_emoe(self, emoe):
        emoe_names = [emoe_rt.emoe.name
                      for emoe_rts in self._emoes_by_client_id.values()
                      for emoe_rt in emoe_rts]

        if emoe.name in emoe_names:
            return False,f'EMOE name "{emoe.name}" already exists.'

        requested = emoe.cpus

        available = self._cpum.num_available

        return requested <= available,f'requested cpus {requested} available cpus {available}'


    def emoe_runtimes_by_client_id(self, client_id):
        return self._emoes_by_client_id.get(client_id, [])


    def start_emoe(self,
                   client_id,
                   emoe,
                   container_listen_address,
                   container_listen_port):
        ok,message = self.check_emoe(emoe)

        if not ok:
            return False,message,None

        num_cpus_requested = emoe.cpus

        cpus = self._cpum.allocate(num_cpus_requested)

        emoe_rt = EmoeRuntime(self._timestamper.next_timestamp,
                              client_id,
                              emoe,
                              cpus,
                              self._config)

        ok = False
        message = ''

        try:
            self._builder.build_config(emoe_rt, self._config)

            ok,message = \
                self._cm.start(emoe_rt,
                               container_listen_address,
                               container_listen_port)

            if ok:
                self._emoes_by_client_id[emoe_rt.client_id].append(emoe_rt)

                self._emoes_by_emoe_id[emoe_rt.emoe_id] = emoe_rt

        finally:
            if not ok:
                self._cpum.deallocate(cpus)

        return ok,message,emoe_rt


    def register_started_container(self, emoe_rt, container):
        emoe_rt.container = container

        logging.info(
            f'started emoe "{emoe_rt.emoe.name}" '
            f'using {emoe_rt.num_cpus} cpus.')


    def handle_failed_container_start(self, emoe_rt):
        message = f'{emoe_rt.emoe.name} failed to start from state {emoe_rt.state.name}'

        logging.error(f'handle_failed_container_start: {message}')

        emoe_rt.state = EmoeState.FAILED

        self._send_container_control_message(emoe_rt, EmoeCommand.STOP)

        self._broker.send_container_state_message_to_client(emoe_rt)

        self._delete_emoe_rt(emoe_rt)


    def stop_emoe(self, client_id, emoe_id):
        emoe_rt = self._emoes_by_emoe_id.get(emoe_id, None)

        if not emoe_rt:
            return False,f'could not find an emoe associated with id {emoe_id}',None

        logging.info(f'Manager.stop_emoe for emoe_id={emoe_id} '
                     f'emoe_name={emoe_rt.emoe.name} '
                     f'state={emoe_rt.state.name}')

        if emoe_rt.state == EmoeState.STOPPING or emoe_rt.state == EmoeState.STOPPED:
            logging.info(f'Ignore request to stop emoe_id={emoe_id} '
                         f'emoe_name={emoe_rt.emoe.name} already stopped')

            return

        emoe_rt.state = EmoeState.STOPPING
        emoe_rt.stop_count = 2

        self._cpum.deallocate(emoe_rt.cpus)

        self._hpm.deallocate(emoe_rt.host_port_mappings.keys())

        # stop the emoe
        self._send_container_control_message(emoe_rt, EmoeCommand.STOP)

        return True,f'stopping emoe "{emoe_rt.emoe.name}".',emoe_rt.emoe.name


    def handle_container_worker_event(self, data):
        self._cm.handle_container_worker_event(data)


    def handle_container_worker_close(self):
        logging.info('handle_container_worker_close')


    def handle_container_state_message(self, container_id, emoe_id, state, detail):
        emoe_rt = self._emoes_by_emoe_id.get(emoe_id, None)

        if not emoe_rt:
            logging.error(f'Received container state message from unknown emoe_id '
                          f'{emoe_id}. Ignoring.')

            return

        logging.info(f'Manager.handle_container_state_message: '\
                     f'emoe_id={emoe_id} current_state={emoe_rt.state.name} new_state={state.name}.')

        # start the emulation on receiving CONNECTED on an QUEUED emoe
        if emoe_rt.state == EmoeState.QUEUED and state == EmoeState.CONNECTED:
            emoe_rt.state = EmoeState.STARTING

            emoe_rt.container_id = container_id

            self._send_container_control_message(emoe_rt, EmoeCommand.START)

            self._broker.send_container_state_message_to_client(emoe_rt, detail)

            logging.debug('STARTING')

        elif emoe_rt.state == EmoeState.STARTING and state == EmoeState.RUNNING:
            emoe_rt.state = EmoeState.RUNNING

            self._broker.send_container_state_message_to_client(emoe_rt, detail)

            logging.debug('RUNNING')

        elif emoe_rt.state < EmoeState.STOPPING and state == EmoeState.STOPPING:
            # tear down the container
            emoe_rt.state = state

            emoe_rt.stop_count = 1

            logging.debug(f'STOPPING {emoe_rt.emoe.name} count:{emoe_rt.stop_count}')

        elif emoe_rt.state == EmoeState.STOPPING:
            if emoe_rt.stop_count < 2:
                emoe_rt.stop_count += 1
                logging.debug(f'STOPPING {emoe_rt.emoe.name} count:{emoe_rt.stop_count}')
                return

            self._broker.send_container_state_message_to_client(emoe_rt, detail)

            logging.debug(f'STOPPING {emoe_rt.emoe.name} count:{emoe_rt.stop_count}')

            self._cm.stop_and_remove(emoe_rt.container)

            # delete directory according to emexdirectory_action configuration itme
            if self._config.emexdirectory_action == 'delete' or \
               self._config.emexdirectory_action == 'deleteonsuccess' and emoe_rt.did_run:
                logging.info(f'emexdirectory action: '
                             f'{self._config.emexdirectory_action} {emoe_rt.workdir}')
                shutil.rmtree(emoe_rt.workdir)

            # delete
            self._delete_emoe_rt(emoe_rt)

        else:
            logging.debug(f'on state message from {emoe_rt.emoe.name}, no action')


    def _delete_emoe_rt(self, emoe_rt):
        self._emoes_by_emoe_id.pop(emoe_rt.emoe_id)

        client_emoe_rts = self._emoes_by_client_id[emoe_rt.client_id]

        client_emoe_rts.pop(client_emoe_rts.index(emoe_rt))


    def _send_container_control_message(self, emoe_rt, command):
        # only send if the container has connected
        if emoe_rt.did_connect:
            logging.info(f'send_container_control_message {emoe_rt.state.name} {emoe_rt.container_id}')
            self._broker.send_container_control_message(emoe_rt.container_id,
                                                        emoe_rt.emoe_id,
                                                        command)
