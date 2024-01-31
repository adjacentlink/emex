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
import socket
import logging

from pandas import DataFrame

from emex.emoemessages import SimpleTrafficFlowType,TrafficProtocolType


class TrafficManager:
    MGEN_PORTMAP_FILE='/tmp/etce/config/doc/mgen_port_map.csv'

    def __init__(self):
        self._flow_index = 0 # unique index per flows row

        self._flows = DataFrame(columns=['flow_index',
                                         'flow_name',
                                         'flow_id',
                                         'source',
                                         'destination',
                                         'tos',
                                         'ttl',
                                         'proto',
                                         'flow_pattern', # periodic,poisson,jitter
                                         'size_bytes',
                                         'packet_rate',
                                         'jitter_fraction'])

        self._flow_number = 1

        self._platform_map = self._read_port_map_file()

        self._flow_count_by_platform = defaultdict(lambda: 1)

        self._mgen_remote_control_sockets = {
            plt_name:None for plt_name in self._platform_map
        }


    def _next_flow_index(self):
        self._flow_index += 1

        return self._flow_index


    @property
    def connected(self):
        """
        The connected state requires an open socket to all mgen instances
        """
        return all(self._mgen_remote_control_sockets.values())


    def _read_port_map_file(self):
        platform_map = {}

        # connect to mgen instances for sending traffic commands
        for plt_num,line in enumerate(open(TrafficManager.MGEN_PORTMAP_FILE, 'r'), start=1):
            line = line.strip()

            if not line:
                continue

            platform,hostname,ipv4address,device = line.split(',')

            platform_map[platform] = (plt_num,hostname,ipv4address,device)

        return platform_map


    def connect(self):
        if self.connected:
            return

        for platform,s in self._mgen_remote_control_sockets.items():
            if s:
                continue

            plt_num,hostname,ipv4address,device = self._platform_map[platform]

            mgen_socket_name = f'/tmp/mgen-{hostname}'

            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

                logging.debug(f'try connecting to mgen instance socket at {mgen_socket_name}')

                s.connect(mgen_socket_name)

                self._mgen_remote_control_sockets[platform] = s

            except FileNotFoundError as fnfe:
                logging.debug(f'{mgen_socket_name} not running yet')


    def _send(self, platform, mgen_event_string):
        logging.debug(f'_send {platform} {mgen_event_string}')

        s = self._mgen_remote_control_sockets[platform]

        s.send(f'event {mgen_event_string}'.encode())


    def get_flows(self):
        logging.debug('get_flows')

        return self._flows


    def _select_sources_and_destinations(self, sources, destinations):
        """ Ensure all sources and destinations (if any) match
            valid platform names.

            Return the platform names that match the specified sources
            and destinations - or all platform names when none are
            specified.
        """
        all_platforms = set(self._platform_map.keys())

        unknown_sources = set(sources).difference(all_platforms)

        if unknown_sources:
            message = f'ignoring unknown traffic sources {unknown_sources}'

            logging.warning(message)

            sources = list(set(sources).difference(unknown_sources))

        # make sure indicated destinations are all known platforms
        unknown_destinations = set(destinations).difference(all_platforms)

        if unknown_destinations:
            message = f'ignoring unknown traffic destinations {unknown_destinations}'

            logging.warning(message)

            destinations = list(set(destinations).difference(unknown_destinations))

        # winnow sources to those provided if any
        flow_sources = set(sources) if sources else all_platforms

        flow_destinations = \
            set(destinations) if destinations else all_platforms

        return True,'',sorted(flow_sources),sorted(flow_destinations)


    def start_flows(self, flow_on_requests):
        logging.debug(f'start_flows flow_on_requests={flow_on_requests}')

        if not self.connected:
            return False,'start_flows called before connected'

        """
        PERIODIC = emexscenario_pb2.SimpleFlow.PERIODIC
        POISSON = emexscenario_pb2.SimpleFlow.POISSON
        JITTER = emexscenario_pb2.SimpleFlow.JITTER

        StartSimpleFlowRequest = \
            namedtuple('StartSimpleFlowRequest',
                       ['flow_name','sources','destinations',
                        'protocol','tos','ttl',
                        'type','size_bytes','packet_rate','jitter_fraction'])
        """

        # make sure all requested flows are valid before processing
        # any of them - take all or none
        valid_request = True
        message = ''

        for request in flow_on_requests:
            if request.flow_name and request.flow_name in self._flows.flow_name.values:
                valid_request = False

                message = f'invalid flow request, flow name {request.flow_name} already exists'

                logging.error(message)

        if not valid_request:
            return False,message

        for request in flow_on_requests:
            flow_name = request.flow_name

            if not flow_name:
                flow_name = f'flow-{self._flow_number:03d}'
                self._flow_number += 1

            ok,message,flow_sources,flow_destinations = \
                self._select_sources_and_destinations(request.sources, request.destinations)

            if not ok:
                return False,message

            flow_ok = None
            flow_message = None
            if request.protocol == TrafficProtocolType.MULTICAST:
                flow_ok,flow_message = \
                    self._start_multicast(flow_name, request, flow_sources, flow_destinations)
            else:
                flow_ok,flow_message = \
                    self._start_unicast(flow_name, request, flow_sources, flow_destinations)

            if not flow_ok:
                return flow_ok,flow_message

        return True,''


    def _start_multicast(self, flow_name, request, flow_sources, flow_destinations):
        logging.debug('_start_mulicast')

        flow_pairs = [(s,flow_destinations) for s in flow_sources]

        for source,destinations in flow_pairs:
            """
            DataFrame(columns=['flow_index',
                               'flow_name',
                               'active',
                               'flow_id',
                               'source',
                               'destination',
                               'tos',
                               'ttl',
                               'proto',
                               'flow_pattern', # periodic,poisson,jitter
                               'size_bytes',
                               'packet_rate',
                               'jitter_fraction'])
            """
            plt_num,_,_,src_device = self._platform_map[source]

            flow_count = self._flow_count_by_platform[source]
            self._flow_count_by_platform[source] += 1

            # change source port for each flow as TTL and TOS are per source port
            src_port = 5000 + flow_count

            flow_id = (plt_num + 100) * 100 + flow_count

            dst_address = f'224.1.1.{plt_num}'

            dst_port = flow_id

            # send the mgen command to the instance
            flow_phrase = None

            if request.type == SimpleTrafficFlowType.PERIODIC:
                flow_phrase = f'PERIODIC [{request.packet_rate:f} {request.size_bytes}]'
            elif request.type == SimpleTrafficFlowType.POISSON:
                flow_phrase =  f'POISSON [{request.packet_rate:f} {request.size_bytes}]'
            else: # SimpleTrafficFlowType.JITTER:
                flow_phrase =  f'JITTER [{request.packet_rate:f} {request.size_bytes} {request.jitter_fraction:f}]'

            for destination in destinations:
                # don't send multicast to same node
                if source == destination:
                    continue

                self._flows = self._flows.append([
                    {'flow_index':self._next_flow_index(),
                     'flow_name':flow_name,
                     'active':True,
                     'flow_id':flow_id,
                     'source':source,
                     'destination':destination,
                     'tos':request.tos,
                     'ttl':request.ttl,
                     'proto':request.protocol,
                     'flow_pattern':request.type,
                     'size_bytes':request.size_bytes,
                     'packet_rate':request.packet_rate,
                     'jitter_fraction':request.jitter_fraction}])

                _,_,_,dst_device = self._platform_map[destination]

                # join the multicast group for multicast
                self._send(destination, f'JOIN {dst_address} INTERFACE {dst_device}')

                self._send(destination, f'LISTEN UDP {dst_port}')

            self._send(source,
                       f'ON {flow_id} '
                       f'UDP DST {dst_address}/{dst_port} '
                       f'{flow_phrase} '
                       f'INTERFACE {src_device} '
                       f'SRC {src_port} '
                       f'TOS 0x{request.tos:x} '
                       f'TTL {request.ttl}')

        logging.info(self._flows)

        return True,f'{flow_name} created.'


    def _start_unicast(self, flow_name, request, flow_sources, flow_destinations):
        logging.debug('_start_unicast')

        # for unicast each source,destination pair is a unique flow
        flow_pairs = [(s,d) for s in flow_sources for d in flow_destinations
                      if not s==d]

        for source,destination in flow_pairs:
            """
            DataFrame(columns=['index',
                               'flow_name',
                               'flow_id',
                               'source',
                               'destination',
                               'tos',
                               'ttl',
                               'proto',
                               'flow_pattern', # periodic,poisson,jitter
                               'size_bytes',
                               'packet_rate',
                               'jitter_fraction'])
            """
            plt_num,_,_,src_device = self._platform_map[source]

            flow_count = self._flow_count_by_platform[source]
            self._flow_count_by_platform[source] += 1

            src_port = 5000 + flow_count

            flow_id = (plt_num + 100) * 100 + flow_count

            dst_port = flow_id

            self._flows = self._flows.append([
                {'flow_index':self._next_flow_index(),
                 'flow_name':flow_name,
                 'active':True,
                 'flow_id':flow_id,
                 'source':source,
                 'destination':destination,
                 'tos':request.tos,
                 'ttl':request.ttl,
                 'proto':request.protocol,
                 'flow_pattern':request.type,
                 'size_bytes':request.size_bytes,
                 'packet_rate':request.packet_rate,
                 'jitter_fraction':request.jitter_fraction}])

            flow_phrase = None

            if request.type == SimpleTrafficFlowType.PERIODIC:
                flow_phrase = f'PERIODIC [{request.packet_rate} {request.size_bytes}]'
            elif request.type == SimpleTrafficFlowType.POISSON:
                flow_phrase = f'POISSON [{request.packet_rate} {request.size_bytes}]'
            else: # SimpleTrafficFlowType.JITTER:
                flow_phrase = f'JITTER [{request.packet_rate} {request.size_bytes} {request.jitter_fraction}]'

            _,_,dst_address,dst_device = self._platform_map[destination]

            self._send(destination, f'LISTEN {request.protocol.name} {dst_port}')

            self._send(source,
                       f'ON {flow_id} '
                       f'{request.protocol.name} '
                       f'SRC {src_port} '
                       f'DST {dst_address}/{dst_port} '
                       f'{flow_phrase} '
                       f'TOS 0x{request.tos:x}')

        logging.info(self._flows)

        return True,''


    def stop_flows(self, flow_off_requests):
        if not self.connected:
            return False,'stop_flows called before connected'

        for request in flow_off_requests:
            # first insure that source and destination names are valid
            ok,message,flow_sources,flow_destinations = \
                self._select_sources_and_destinations(request.sources, request.destinations)

            if not ok:
                return False,message

            for request in flow_off_requests:
                df = self._flows

                if request.flow_name:
                    df = df.loc[df.flow_name == request.flow_name]

                if request.flow_ids:
                    df = df.loc[map(lambda x: x in request.flow_ids, df.flow_id)]

                if request.sources:
                    df = df.loc[map(lambda x: x in request.sources, df.source)]

                if request.destinations:
                    df = df.loc[map(lambda x: x in request.destinations, df.destination)]

                for _,row in df.iterrows():
                    self._send(row.source, f'OFF {row.flow_id}')

                    dst_port = row.flow_id

                    self._send(row.destination, f'IGNORE {dst_port}')

                    self._flows.loc[self._flows.flow_index == row.flow_index, 'active'] = False


                # For the case where only the flow_name is specified,
                # delete all flows associated with the flow_name. This
                # case should cleanly cover removing all rows with flow_name
                # and allow the flow name to be reused.
                if request.flow_name and \
                   not request.flow_ids and \
                   not request.sources and \
                   not request.destinations:
                    self._flows.drop(self._flows.loc[self._flows.flow_name==request.flow_name].index,
                                     inplace=True)

        logging.info(self._flows)

        return True,''
