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

from collections import namedtuple
import copy
import logging
import multiprocessing
import os
import struct
import traceback

from lxml import etree

from waveform_resource.interface.plugin import Plugin as BasePlugin

import emex
from emex.common_pb2 import PASS,FAIL
from emex import emexd_pb2
from emex import emexcontainer_pb2
from emex.manager import Manager
from emex.emoe import Emoe
from emex.emoestate import EmoeState
from emex.utils import numstr_to_numlist


class Plugin(BasePlugin):
    CONTAINER_WORKER_ADDRESS = '127.0.0.1'
    CONTAINER_WORKER_PORT = 49900

    # emexd will look at this location when the user does not specify a
    # configuration file. No configuration file is required.
    DEFAULT_CONFIGURATION_FILE = '/etc/emexd.xml'

    # Default address and port to listen for clients
    DEFAULT_CLIENT_LISTEN_ADDRESS = '127.0.0.1'
    DEFAULT_CLIENT_LISTEN_PORT = 49901

    # Default address and port to listen for launched containers
    DEFAULT_CONTAINER_LISTEN_ADDRESS = '172.17.0.1' # standard docker0 address
    DEFAULT_CONTAINER_LISTEN_PORT = 49902

    # Default switch to enable/disable sending unsolicited container
    # state transition messages to clients.
    DEFAULT_STATE_MESSAGES_ENABLE = False

    # Default range of host ports allocated to map to container
    # service ports
    DEFAULT_ALLOWED_MIN_HOST_PORT = 9000
    DEFAULT_ALLOWED_MAX_HOST_PORT = 9999

    # Default docker image used for running EMOEs
    DEFAULT_DOCKER_IMAGE = 'emex:0.6.3'

    # Defaultl log level for the container daemon
    DEFAULT_EMEXCONTAINERD_LOGLEVEL = 'info'

    DEFAULT_STOP_ALL_CONTAINERS = True

    DEFAULT_EMEXDIRECTORY_ACTION = 'keep'

    DEFAULT_CONTAINER_DATETIME_TAG_FORMAT = 'prefix'

    DEFAULT_NUM_CONTAINER_WORKERS = 1

    Config = namedtuple('Config', ['client_listen_address',
                                   'client_listen_port',
                                   'container_listen_address',
                                   'container_listen_port',
                                   'state_messages_enable',
                                   'allowed_cpus_set',
                                   'allowed_host_ports_set',
                                   'docker_image',
                                   'emexcontainerd_loglevel',
                                   'stop_all_containers',
                                   'emexdirectory_action',
                                   'container_datetime_tag_format',
                                   'num_container_workers'])

    def initialize(self, ctx, configuration_file):
        """Initializes the container daemon.

        Args:
          ctx (obj) Context instance.

          configuration_file (str): Plugin configuration files.

        Raises:
          RuntimeError: If a schema error or configuration error occurs.

        """
        logging.info('initialize')

        if not configuration_file and os.path.isfile(Plugin.DEFAULT_CONFIGURATION_FILE):
            configuration_file = Plugin.DEFAULT_CONFIGURATION_FILE

        if configuration_file:
            logging.info(f'Running emexd from configuration file "{configuration_file}"')

        self._config = self._read_config(configuration_file)

        self._ctx = ctx

        self._client_cache_data = {}

        self._client_sockets = {}

        ctx.create_channel_tcp_server(
            local=self._config.client_listen_address,
            local_port=self._config.client_listen_port,
            on_accept = self._process_client_accept,
            on_message = self._process_client_request,
            on_close = self._reset_client)

        logging.info(f'listening for clients on {self._config.client_listen_address}:'
                     f'{self._config.client_listen_port}')

        self._tcp_container_id = \
            ctx.create_channel_tcp_server(
                local=self._config.container_listen_address,
                local_port=self._config.container_listen_port,
                on_accept = self._process_container_accept,
                on_message = self._process_container_message,
                on_close = self._process_container_close)

        logging.info(f'listening for containers on {self._config.container_listen_address}:'
                     f'{self._config.container_listen_port}')

        ctx.create_channel_tcp_server(
            local=Plugin.CONTAINER_WORKER_ADDRESS,
            local_port=Plugin.CONTAINER_WORKER_PORT,
            on_accept = self._log_container_worker_accept,
            on_message = self._process_container_worker_event,
            on_close = self._handle_container_worker_close)

        self._m = Manager(self,
                          self._config,
                          (Plugin.CONTAINER_WORKER_ADDRESS, Plugin.CONTAINER_WORKER_PORT))


    def start(self,ctx):
        """Starts the service.

        Args:
           ctx (obj): Context instance.
        """
        if self._config.stop_all_containers:
            logging.info('stopping all existing emex containers')

            self._m.reset()


    def stop(self,ctx):
        """Stops the service.

        Args:
          ctx (obj): Context instance.
        """
        logging.info('stop')

        if self._config.stop_all_containers:
            logging.info('stopping all existing emex containers')

            self._m.reset_synchronous()
        else:
            logging.info('stopping all client containers')

            self._m.stop_client_containers_synchronous()


    def destroy(self,ctx):
        """Destroys the service.

        Args:
          ctx (obj): Context instance.

        """
        logging.info('destroy')


    def _process_client_accept(self, ctx, channel_id, client_endpoint, **kwargs):
        ip,port = client_endpoint

        client_id = (channel_id, client_endpoint)

        self._client_sockets[client_id] = kwargs['remote']

        logging.info(f'process accept channel_id: {channel_id} ' \
                     f'endpoint: {ip}:{port}')

        self._reset_client(ctx, channel_id, client_endpoint)


    def _process_client_request(self, ctx, channel_id, data, remote):
        ip,port = remote

        client_id = (channel_id, remote)

        cache_data = self._client_cache_data.get(client_id, '')

        if cache_data:
            data = cache_data + data
            self._client_cache_data[client_id] = ''

        while data:
            if len(data) < 4:
                self._client_cache_data[client_id] = copy.copy(data)

                return

            (count,) = struct.unpack('!I', data[:4])

            if count > len(data[4:]):
                self._client_cache_data[client_id] = copy.copy(data)

                return

            (request_str,) = struct.unpack('%ds' % count, data[4:count+4])

            request = emexd_pb2.ClientMessage()

            request.ParseFromString(request_str)

            logging.debug(f'process request channel_id: {channel_id} ' \
                          f'remote: {ip}:{port} of {count} bytes and ' \
                          f'message type {emexd_pb2.ClientMessage.MODEL_TYPES_REQUEST_TYPE}')

            if request.type == emexd_pb2.ClientMessage.MODEL_TYPES_REQUEST_TYPE:
                reply = self._handle_models_request()

            elif request.type == emexd_pb2.ClientMessage.CHECK_EMOE_REQUEST_TYPE:
                reply = self._handle_check_emoe(request)

            elif request.type == emexd_pb2.ClientMessage.START_EMOE_REQUEST_TYPE:
                reply = self._handle_start_emoe(client_id, request);

            elif request.type == emexd_pb2.ClientMessage.LIST_EMOES_REQUEST_TYPE:
                reply = self._handle_list_emoes(client_id)

            elif request.type == emexd_pb2.ClientMessage.STOP_EMOE_REQUEST_TYPE:
                reply = self._handle_stop_emoe(client_id, request)

            reply_str = reply.SerializeToString()

            format_str = '!I%ds' % len(reply_str)

            bufstr = struct.pack(format_str, len(reply_str), reply_str)

            ctx.channel_send(channel_id, bufstr, remote=remote)

            data = data[count+4:]


    def _reset_client(self, ctx, channel_id, client_endpoint):
        client_id = (channel_id, client_endpoint)

        self._m.reset_client(client_id)


    def _read_config(self, configuration_file):
        client_listen_address = Plugin.DEFAULT_CLIENT_LISTEN_ADDRESS

        client_listen_port = Plugin.DEFAULT_CLIENT_LISTEN_PORT

        container_listen_address = Plugin.DEFAULT_CONTAINER_LISTEN_ADDRESS

        container_listen_port = Plugin.DEFAULT_CONTAINER_LISTEN_PORT

        state_messages_enable = Plugin.DEFAULT_STATE_MESSAGES_ENABLE

        num_host_cpus = int(multiprocessing.cpu_count())

        # by default, allocate all cpus except for the minimum of
        # the first 1/4 ids, or the first 8.
        min_cpu_id = min(num_host_cpus//4, 8)

        allowed_cpus_set = set(range(min_cpu_id, num_host_cpus))

        allowed_host_ports_set = set(range(Plugin.DEFAULT_ALLOWED_MIN_HOST_PORT,
                                           Plugin.DEFAULT_ALLOWED_MAX_HOST_PORT+1))

        docker_image = Plugin.DEFAULT_DOCKER_IMAGE

        emexcontainerd_loglevel = Plugin.DEFAULT_EMEXCONTAINERD_LOGLEVEL

        stop_all_containers = Plugin.DEFAULT_STOP_ALL_CONTAINERS

        emexdirectory_action = Plugin.DEFAULT_EMEXDIRECTORY_ACTION

        container_datetime_tag_format = Plugin.DEFAULT_CONTAINER_DATETIME_TAG_FORMAT

        num_container_workers = Plugin.DEFAULT_NUM_CONTAINER_WORKERS

        if not configuration_file:
            config = Plugin.Config(client_listen_address,
                                   client_listen_port,
                                   container_listen_address,
                                   container_listen_port,
                                   state_messages_enable,
                                   allowed_cpus_set,
                                   allowed_host_ports_set,
                                   docker_image,
                                   emexcontainerd_loglevel,
                                   stop_all_containers,
                                   emexdirectory_action,
                                   container_datetime_tag_format,
                                   num_container_workers)

            self._log_config(config)

            return config

        tree = etree.parse(configuration_file)

        root = tree.getroot()

        schemafile = None

        for emexpath in emex.__path__:
            schemafile = os.path.join(emexpath, 'emexd.xsd')

            logging.info(f'testing schemafile {schemafile}')

            if os.path.isfile(schemafile):
                logging.info('found')
                break

        if not schemafile:
            raise RuntimeError('Could not find emexd schema file "emexd.xsd"')

        logging.info(f'parsing schemafile {schemafile}')

        schemadoc = etree.parse(schemafile)

        schema = etree.XMLSchema(etree=schemadoc, attribute_defaults=True)

        if not schema(root):
            message = []

            for entry in schema.error_log:
                message.append('{}: {}'.format(entry.line,entry.message))

            raise RuntimeError('\n'.join(message))

        client_listen_elems = root.xpath('/emexd/client-listen')

        if client_listen_elems:
            client_listen_address = client_listen_elems[0].get('address')
            client_listen_port = int(client_listen_elems[0].get('port'))

        container_listen_elems = root.xpath('/emexd/container-listen')

        if container_listen_elems:
            print(container_listen_elems)
            container_listen_address = container_listen_elems[0].get('address')
            container_listen_port = int(container_listen_elems[0].get('port'))

        state_messages_elems = root.xpath('/emexd/state-messages')

        if state_messages_elems:
            state_messages_enable = state_messages_elems[0].get('enable') == 'true'

        allowed_cpus_elems = root.xpath('/emexd/allowed-cpus')

        if allowed_cpus_elems:
            num_str = allowed_cpus_elems[0].get('ids')

            allowed_cpus_set = set(numstr_to_numlist(num_str))

            max_cpu_id = max(allowed_cpus_set)
            if max_cpu_id >= num_host_cpus:
                logging.warning(f'Setting maximum allocated cpu to the maximum '
                                f'id available on the system ({num_host_cpus-1}), '
                                f'because the configured value ({max_cpu_id}) exceeds it.')
                max_cpu_id = num_host_cpus

            min_cpu_id = min(allowed_cpus_set)
            if min_cpu_id < 1:
                logging.warning(f'Will not allocate cpu id 0 as configured. '
                                f'Setting to 1.')
                min_cpu_id = 1

            allowed_cpus_set.intersection_update(set(range(min_cpu_id, max_cpu_id)))

        allowed_host_ports_elems = root.xpath('/emexd/allowed-host-ports')

        if allowed_host_ports_elems:
            num_str = allowed_host_ports_elems[0].get('ports')

            allowed_host_ports_set = set(numstr_to_numlist(num_str))

        docker_image_elems = root.xpath('/emexd/docker-image')

        if docker_image_elems:
            docker_image = docker_image_elems[0].get('name')

        emexcontainerd_loglevel_elems = root.xpath('/emexd/emexcontainerd-loglevel')

        if emexcontainerd_loglevel_elems:
            emexcontainerd_loglevel = emexcontainerd_loglevel_elems[0].get('level')

        stop_all_containers_elems = root.xpath('/emexd/stop-all-containers')

        if stop_all_containers_elems:
            stop_all_containers = stop_all_containers_elems[0].get('enable') == 'true'

        emexdirectory_elems = root.xpath('/emexd/emexdirectory')

        if emexdirectory_elems:
            emexdirectory_action = emexdirectory_elems[0].get('action')


        container_datetime_tag_elems = root.xpath('/emexd/container-datetime-tag')

        if container_datetime_tag_elems:
            container_datetime_tag_format = container_datetime_tag_elems[0].get('format')

        num_container_workers_elems = root.xpath('/emexd/container-workers')

        if num_container_workers_elems:
            num_container_workers = int(num_container_workers_elems[0].get('count'))

        config = Plugin.Config(client_listen_address,
                               client_listen_port,
                               container_listen_address,
                               container_listen_port,
                               state_messages_enable,
                               allowed_cpus_set,
                               allowed_host_ports_set,
                               docker_image,
                               emexcontainerd_loglevel,
                               stop_all_containers,
                               emexdirectory_action,
                               container_datetime_tag_format,
                               num_container_workers)

        self._log_config(config)

        return config


    def _log_config(self, config):
        logging.info(f'client_address={config.client_listen_address}')

        logging.info(f'client_port={config.client_listen_port}')

        logging.info(f'container_address={config.container_listen_address}')

        logging.info(f'container_port={config.container_listen_port}')

        logging.info(f'state_messages_enable={config.state_messages_enable}')

        logging.info(f'allowed_cpus={config.allowed_cpus_set}')

        logging.info(f'allowed_host_ports bounds '
                     f'[{min(config.allowed_host_ports_set)}, '
                     f'{max(config.allowed_host_ports_set)}]')

        logging.info(f'docker_image={config.docker_image}')

        logging.info(f'emexcontainerd_loglevel={config.emexcontainerd_loglevel}')

        logging.info(f'stop_all_containers={config.stop_all_containers}')

        logging.info(f'emexdirectory_action={config.emexdirectory_action}')

        logging.info(f'container_datetime_tag_format={config.container_datetime_tag_format}')

        logging.info(f'num_container_workers={config.num_container_workers}')


    def _unpack_emoe(self, emoe_proto):
        platformtypes,antennatypes = self._m.get_models()

        # this implicitly checks that
        # all platforms have an ok number of waveforms
        # all waveform parameters have an assigned value
        return Emoe.from_protobuf(emoe_proto,
                                  antennatypes,
                                  platformtypes)


    def _handle_models_request(self):
        logging.info('received modelTypesRequest')

        reply = emexd_pb2.ServerMessage()

        reply.type = emexd_pb2.ServerMessage.MODEL_TYPES_REPLY_TYPE

        platformtypes,antennatypes = self._m.get_models()

        for _,ptype in platformtypes.items():
            ptype.to_protobuf(reply.modelTypesReply.platformtypes.add())

        for _,atype in antennatypes.items():
            atype.to_protobuf(reply.modelTypesReply.antennatypes.add())

        logging.info('sending modelTypesReply')

        return reply


    def _handle_check_emoe(self, request):
        emoe_name = request.checkEmoeRequest.emoe_name

        logging.info(f'received checkEmoeRequest for emoe "{emoe_name}" '
                     f'with {len(request.checkEmoeRequest.emoe.platforms)} platforms.')

        reply = emexd_pb2.ServerMessage()

        reply.type = emexd_pb2.ServerMessage.CHECK_EMOE_REPLY_TYPE

        ok = True

        message = 'ok'

        try:
            emoe = self._unpack_emoe(request.checkEmoeRequest.emoe)

            ok,message = self._m.check_emoe(emoe)
        except Exception as e:
            ok = False
            logging.error(traceback.format_exc())
            message = str(e)

        reply.checkEmoeReply.emoe_name = emoe_name

        reply.checkEmoeReply.result = PASS if ok else FAIL

        reply.checkEmoeReply.message = message

        resultstr = 'PASS' if ok else 'FAIL'

        logging.info(f'sending checkEmoeReply {resultstr} for emoe '
                     f'"{emoe_name}"')

        return reply


    def _handle_start_emoe(self, client_id, request):
        emoe_name = request.startEmoeRequest.emoe_name

        logging.info(f'received startEmoeRequest from client {client_id} '
                     f'for emoe "{emoe_name}" '
                     f'with {len(request.startEmoeRequest.emoe.platforms)} platforms.')

        reply = emexd_pb2.ServerMessage()

        reply.type = emexd_pb2.ServerMessage.START_EMOE_REPLY_TYPE

        ok = True

        message = 'ok'

        try:
            emoe = self._unpack_emoe(request.startEmoeRequest.emoe)

            ok,message,emoe_rt = self._m.start_emoe(client_id,
                                                    emoe,
                                                    self._config.container_listen_address,
                                                    self._config.container_listen_port)
        except Exception as e:
            ok = False
            logging.error(traceback.format_exc())
            message = str(e)

        reply.startEmoeReply.emoe_name = emoe_name

        reply.startEmoeReply.result = PASS if ok else FAIL

        reply.startEmoeReply.message = message

        if ok:
            reply.startEmoeReply.handle = str(emoe_rt.emoe_id)

            logging.info(f'sending startEmoeReply PASS for emoe '
                         f'name:{emoe_rt.emoe.name} handle:{emoe_rt.emoe_id}')
        else:
            logging.info(f'sending startEmoeReply FAIL for emoe '
                         f'name:{emoe_name}')

        return reply


    def _handle_list_emoes(self, client_id):
        logging.info(f'received listEmoesRequest from client {client_id}')

        reply = emexd_pb2.ServerMessage()

        reply.type = emexd_pb2.ServerMessage.LIST_EMOES_REPLY_TYPE

        for emoe_rt in self._m.emoe_runtimes_by_client_id(client_id):
            entry = reply.listEmoesReply.entries.add()

            entry.handle = emoe_rt.emoe_id

            entry.emoe_name = emoe_rt.emoe.name

            entry.state = emoe_rt.state.value

            entry.assigned_cpus = len(emoe_rt.cpus)

            # no accessors for EMOEs that have advances past the UPDATING state
            if emoe_rt.state > EmoeState.UPDATING:
                continue

            local_address,_ = self._client_sockets[client_id].getsockname()

            for host_port,(service_name,_) in emoe_rt.host_port_mappings.items():
                emoe_accessor_proto = entry.emoe_accessors.add()

                emoe_accessor_proto.service_name = service_name

                emoe_accessor_proto.ip_address = local_address

                emoe_accessor_proto.port = host_port

        reply.listEmoesReply.total_cpus = self._m.total_cpus

        reply.listEmoesReply.available_cpus = self._m.available_cpus

        return reply


    def _handle_stop_emoe(self, client_id, request):
        emoe_id = request.stopEmoeRequest.handle

        logging.info(f'received stopEmoeRequest from client {client_id} '
                     f'for emoe "{emoe_id}"')

        reply = emexd_pb2.ServerMessage()

        reply.type = emexd_pb2.ServerMessage.STOP_EMOE_REPLY_TYPE

        ok = True

        message = 'ok'

        ok,message,emoe_name = self._m.stop_emoe(client_id, emoe_id)

        #except:
        #    ok = False

        reply.stopEmoeReply.handle = str(emoe_id)

        reply.stopEmoeReply.emoe_name = str(emoe_name)

        reply.stopEmoeReply.result = PASS if ok else FAIL

        reply.stopEmoeReply.message = message

        if ok:
            logging.info(f'sending stopEmoeReply PASS for emoe '
                         f'name:{emoe_name} handle:{emoe_id}')
        else:
            logging.info(f'sending stopEmoeReply FAIL for emoe '
                         f'name:{emoe_name}')

        return reply


    def _process_container_accept(self, ctx, channel_id, container_endpoint, **kwargs):
        ip,port = container_endpoint

        logging.debug(f'_process_container_accept on {channel_id} from {ip}:{port}')


    def _process_container_message(self, ctx, channel_id, data, remote):
        ip,port = remote

        logging.debug(f'_process_container_message on {channel_id} from {ip}:{port}')

        (count,) = struct.unpack('!I', data[:4])

        try:
            (message_str,) = struct.unpack('%ds' % count, data[4:])
        except struct.error as se:
            logging.warning(f'Error on receiving malformed message "{se}"')

            return

        message = emexcontainer_pb2.ContainerStateMessage()

        message.ParseFromString(message_str)

        state = EmoeState(message.state)

        container_id = (channel_id, remote)

        self._m.handle_container_state_message(container_id,
                                               message.emoe_id,
                                               state,
                                               message.message)


    def send_container_control_message(self, container_id, emoe_id, command):
        message = emexcontainer_pb2.ContainerControlMessage()

        message.command = command.value

        message.emoe_id = emoe_id

        message_str = message.SerializeToString()

        format_str = '!I%ds' % len(message_str)

        bufstr = struct.pack(format_str, len(message_str), message_str)

        logging.info(f'send {command.name} command to emoe: {emoe_id}')

        channel_id,remote = container_id

        self._ctx.channel_send(channel_id, bufstr, remote=remote)


    def send_container_state_message_to_client(self,
                                               emoe_rt,
                                               detail=None):
        # Only send unsolicited container state messages when
        # enabled to do so
        if not self._config.state_messages_enable:
            return

        reply = emexd_pb2.ServerMessage()

        reply.type = emexd_pb2.ServerMessage.EMOE_STATE_TRANSITION_EVENT


        # required string handle = 1;
        # required string emoe_name = 2;
        # required EmoeState state = 3;
        # repeated EmoeAccessor emoe_accessors = 4;
        # optional uint32 assigned_cpus = 5;
        # optional string message = 6;
        reply.emoeStateTransitionEvent.handle = str(emoe_rt.emoe_id)
        reply.emoeStateTransitionEvent.emoe_name = emoe_rt.emoe.name
        reply.emoeStateTransitionEvent.state = emoe_rt.state.value

        # no accessors for EMOEs that have advances past the UPDATING state
        if emoe_rt.state > EmoeState.UPDATING:
            for host_port,(service_name,_) in emoe_rt.host_port_mappings.items():
                emoe_accessor_proto = reply.emoeStateTransitionEvent.emoe_accessors.add()

                emoe_accessor_proto.service_name = service_name

                emoe_accessor_proto.ip_address = self._config.client_listen_address

                emoe_accessor_proto.port = host_port

        reply.emoeStateTransitionEvent.assigned_cpus = emoe_rt.emoe.cpus

        if detail:
            reply.emoeStateTransitionEvent.message = detail

        logging.info(f'sending emoeStateTransitionEvent for emoe name: {emoe_rt.emoe.name} ' \
                     f'id: {emoe_rt.emoe_id} state: {emoe_rt.state.name}')

        reply_str = reply.SerializeToString()

        format_str = '!I%ds' % len(reply_str)

        bufstr = struct.pack(format_str, len(reply_str), reply_str)

        channel_id, remote = emoe_rt.client_id

        try:
            self._ctx.channel_send(channel_id, bufstr, remote=remote)
        except ValueError as ve:
            logging.warning(ve)


    def _process_container_close(self, ctx, channel_id, container_endpoint):
        logging.info(f'closed connection on channel {channel_id}')


    def _log_container_worker_accept(self, ctx, channel_id, container_endpoint, **kwargs):
        ip,port = container_endpoint

        logging.debug(f'_log_container_worker_accept on {channel_id} from {ip}:{port}')


    def _process_container_worker_event(self, ctx, channel_id, data, remote):
        self._m.handle_container_worker_event(data)


    def _handle_container_worker_close(self, ctx, channel_id, container_endpoint):
        self._m.handle_container_worker_close()

