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

"""Waveform Resource Plugin implementation of the EMEX Daemon.
The Daemon launches containers on the local host at the request
of an EMEX client.
"""

from __future__ import absolute_import, division, print_function

import os
import json
import logging
import shlex
import socket
import struct
import subprocess
import time


from emex.emoestate import EmoeState
from emex.emexcontainer_pb2 import ContainerControlMessage,ContainerStateMessage
from waveform_resource.interface.plugin import Plugin as BasePlugin
from emex.scenarioservermessagehandler import ScenarioServerMessageHandler
from emex.scenariomanager import ScenarioManager


class Plugin(BasePlugin):
    DEFAULT_ETCE_STATUSMCAST_ADDRESS = '224.1.2.8'
    DEFAULT_ETCE_STATUSMCAST_PORT = 48101
    DEFAULT_ETCE_STATUSMCAST_DEVICE = 'lo'
    DEFAULT_EMEX_SCENARIO_LISTEN_PORT = 3000


    def initialize(self, ctx, configuration_file):
        """Initializes the container daemon.

        Args:
          ctx (obj) Context instance.

          configuration_file (str): Plugin configuration files.

        Raises:
          RuntimeError: If a schema error is encountered.

        """
        logging.info(f'initialize')

        emexd_address = os.environ['EMEXD_LISTEN_ADDRESS']

        emexd_port = os.environ['EMEXD_LISTEN_PORT']

        etce_statusmcast_address = \
            os.environ.get('ETCE_STATUSMCAST_ADDRESS',
                           Plugin.DEFAULT_ETCE_STATUSMCAST_ADDRESS)

        etce_statusmcast_port = \
            int(os.environ.get('ETCE_STATUSMCAST_PORT',
                               Plugin.DEFAULT_ETCE_STATUSMCAST_PORT))

        etce_statusmcast_device = \
            os.environ.get('ETCE_STATUSMCAST_DEVICE',
                           Plugin.DEFAULT_ETCE_STATUSMCAST_DEVICE)

        emex_scenario_listen_port = \
            int(os.environ.get('EMEX_SCENARIO_LISTEN_PORT',
                               Plugin.DEFAULT_EMEX_SCENARIO_LISTEN_PORT))

        self._service_endpoint = (emexd_address, int(emexd_port))

        self._emoe_id = os.environ['EMOE_ID']

        self._state = EmoeState.QUEUED

        # maintain a status variable to indicate whether the EMOE reached
        # the running state
        self._did_run = False

        self._ctx = ctx

        self._sm = ScenarioManager(self)

        self._scenario_message_handler = ScenarioServerMessageHandler()

        self._emexd_channel_id = None

        self._cache_data = ''

        logging.info(f'connecting to emexd at {emexd_address}:'
                     f'{emexd_port} with emoe_id {self._emoe_id}')

        ctx.create_channel_tcp_client(remote=emexd_address,
                                      remote_port=int(emexd_port),
                                      on_connect=self._on_connect_emexd,
                                      on_message=self._handle_controller_message,
                                      on_close=self._handle_container_close)

        ctx.create_channel_multicast(group = etce_statusmcast_address,
                                     group_port = etce_statusmcast_port,
                                     device = etce_statusmcast_device,
                                     on_message = self._handle_etce_status_message)

        self._scenario_channel_id = None

        ctx.create_channel_tcp_server(
            local=socket.gethostbyname(socket.gethostname()),
            local_port=emex_scenario_listen_port,
            on_accept = self._process_scenario_client_accept,
            on_message = self._handle_scenario_message,
            on_close = self._on_scenario_close)


        ctx.create_timer(time.time()+5, self._handle_heartbeat_timer)

        self._run_process = None

        self._stop_process = None


    def start(self,ctx):
        """Starts the service.

        Args:
           ctx (obj): Context instance.
        """
        logging.info('start')


    def stop(self,ctx):
        """Stops the service.

        Args:
          ctx (obj): Context instance.
        """
        logging.info('stop')


    def destroy(self,ctx):
        """Destroys the service.

        Args:
          ctx (obj): Context instance.

        """
        logging.info('destroy')


    def change_state(self, new_state, detail=None):
        if not self._state == new_state:
            logging.info(f'change state from {self._state.name} to {new_state.name}')

        self._state = new_state

        if new_state == EmoeState.RUNNING:
            self._did_run = True

        if new_state >= EmoeState.STOPPED:
            self._sm.clean_up(self._did_run)

        self._send_state(detail)


    def _send_state(self, detail=None):
        if self._state < EmoeState.CONNECTED:
            logging.error(f'trying to send state "{self._state.name}" to controller '
                          f'before connected')

            return

        # send current state
        message = ContainerStateMessage()

        message.state = self._state.value

        message.emoe_id = self._emoe_id

        if detail:
            message.message = detail

        message_str = message.SerializeToString()

        format_str = '!I%ds' % len(message_str)

        bufstr = struct.pack(format_str, len(message_str), message_str)

        logging.info(f'send state message {self._state.name} for emoe_id {self._emoe_id}')

        self._ctx.channel_send(self._emexd_channel_id, bufstr, remote=self._service_endpoint)


    def _on_connect_emexd(self, ctx, channel_id, remote):
        self._emexd_channel_id = channel_id

        logging.info('connected')

        self.change_state(EmoeState.CONNECTED)


    def _handle_controller_message(self, ctx, channel_id, data):
        logging.debug(f'_handle_controller_message channel_id={channel_id}')

        (count,) = struct.unpack('!I', data[:4])

        (message_str,) = struct.unpack('%ds' % count, data[4:])

        message = ContainerControlMessage()

        message.ParseFromString(message_str)

        logging.info(f'process control message on channel_id: {channel_id}')

        if not message.emoe_id == self._emoe_id:
            logging.error(f'message emoe_id {message.emoe_id} does not match container emoe_id {self._emoe_id}. '
                          f'ignoring command')

        if message.command == ContainerControlMessage.START:
            logging.info(f'received controller command START for emoe id {message.emoe_id}')

            self._handle_start()

        elif message.command == ContainerControlMessage.STOP:
            logging.info(f'received controller command STOP for emoe id {message.emoe_id}')

            self._handle_stop()

        else:
            logging.error(f'Unknown ContainerControlMessage command {message.command}. '
                          'Ignoring.')
            return


    def _handle_etce_status_message(self, ctx, channel_id, data):
        logging.debug(f'_handle_etce_status_message channel_id={channel_id}')

        data_json = json.loads(data.decode())

        # wait for etce status message
        logging.info('received etce state message type "%s"' % str(data_json))

        etce_step = data_json['step']

        etce_message = data_json['message']

        if etce_step.upper() == 'ERROR':
            self.change_state(EmoeState.STOPPING,
                              detail=f'execution error: "{etce_message}"')

            # just return, controller daemon will tear this container down
            return


        if etce_step.upper() == 'TRAFFIC.RUN':
            if self._state == EmoeState.STARTING:
                if self._sm.connect():
                    self.change_state(EmoeState.RUNNING)


    def _process_scenario_client_accept(self, ctx, channel_id, remote):
        logging.debug('_process_scenario_client_accept')

        # only allow a single scenario client at a a time
        if not self._scenario_channel_id:
            self._scenario_channel_id = channel_id

            ip,port = remote

            self._cache_data = ''

            logging.info(f'accept scenario client on channel_id: {channel_id} ' \
                         f'endpoint: {ip}:{port}')
        else:
            ip,port = remote

            logging.error(f'received connect from a second client on channel_id: {channel_id} ' \
                          f'from endpoint: {ip}:{port}. Quitting.')

            self._handle_stop()


    def _handle_scenario_message(self, ctx, channel_id, data, remote):
        logging.debug(f'_handle_scenario_message channel_id={channel_id} len(data)={len(data)}')

        if not channel_id == self._scenario_channel_id:
            logging.error(f'New channel_id {channel_id} does not match current client {self._scenario_channel_id}.')

        if self._cache_data:
            data = self._cache_data + data
            self._cache_data = ''

        while data:
            if len(data) < 4:
                self._cache_data = data
                return

            (count,) = struct.unpack('!I', data[:4])

            if count > len(data[4:]):
                self._cache_data = data
                return

            (request_str,) = struct.unpack('%ds' % count, data[4:count+4])

            client_sequence,requests = \
                self._scenario_message_handler.parse_client_request(request_str)

            logging.debug(f'received scenario request: client_sequence={client_sequence}')

            self._sm.handle_requests(remote, client_sequence, requests)

            data = data[count+4:]


    def _handle_start(self):
        # start the emulation if we are in the CONNECTED state
        if not self._state == EmoeState.CONNECTED:
            logging.error('received emexd start message while in state "%s". ignoring.' \
                          % self._state.name)

            return

        # start containers and applications
        # etce-test run --kill none emex /tmp/etce/config/doc/hostfile /tmp/etce/config
        self._run_process = subprocess.Popen(shlex.split('/opt/run-etce.sh'),
                                             stdout=open('/tmp/etce/etce.log', 'w'),
                                             stderr=subprocess.STDOUT)

        self.change_state(EmoeState.STARTING)


    def _stop_emulation(self):
        # stop the emulation if we are RUNNING
        if self._run_process:
            self._run_process.kill()

            self._stop_process = subprocess.Popen(shlex.split('etce-lxc stop'),
                                                  stdout=open('/tmp/etce/etcestop.log', 'w'),
                                                  stderr=subprocess.STDOUT)

    def _handle_stop(self):
        logging.info('handle_stop')

        if self._state == EmoeState.STARTING or \
           self._state == EmoeState.RUNNING or \
           self._state == EmoeState.UPDATNG:
            self._stop_emulation()

            self.change_state(EmoeState.STOPPED)


    def _handle_container_close(self, ctx, channel_id, container_endpoint):
        logging.info(f'closed container channel {self._emexd_channel_id}')

        #ctx.delete_channel(self._emexd_channel_id)


    def _handle_heartbeat_timer(self, ctx, timer_id):
        logging.info('heartbeat')

        if self._state == EmoeState.STARTING:
            if self._sm.connect():
                self.change_state(EmoeState.RUNNING)

        elif self._state == EmoeState.STOPPED:
            logging.info('heartbeat timer stopped on STOPPED')

            return

        else:
            self._send_state()

        ctx.create_timer(time.time()+5, self._handle_heartbeat_timer)


    def send_result(self, remote, client_sequence, result, message, flows_df):
        logging.debug(f'send_traffic_result result={result} message={message}')

        reply_str =\
            self._scenario_message_handler.build_result(client_sequence,
                                                        result,
                                                        message,
                                                        flows_df)

        self._send_scenario_reply(remote, reply_str)


    def _send_scenario_reply(self, remote, reply_str):
        logging.debug(f'_send_scenario_reply {remote}')

        format_str = '!I%ds' % len(reply_str)

        message = struct.pack(format_str, len(reply_str), reply_str)

        self._ctx.channel_send(self._scenario_channel_id, message, remote=remote)

        logging.debug(f'_send_scenario_reply {remote} sent')


    def _on_scenario_close(self, ctx, channel_id, remote):
        if self._scenario_channel_id:
            logging.info(f'_on_scenario_close close channel_id={self._scenario_channel_id} '
                         f'remote={remote}')

            self._scenario_channel_id = None
