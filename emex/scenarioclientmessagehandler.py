# Copyright (c) 2022 - Adjacent Link LLC, Bridgewater, New Jersey
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of Adjacent Link LLC nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
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
from pandas import DataFrame

from emex.common_pb2 import PASS,FAIL
import emex.emexscenario_pb2 as emexscenario_pb2


class ScenarioClientMessageHandler:
    def __init__(self, list_flows_flag=False):
        self._send_sequence = 0

        self._list_flows_flag = list_flows_flag


    def _next_sequence(self):
        self._send_sequence += 1
        return self._send_sequence


    def build_client_message(self, eventdict):
        client_request_proto = emexscenario_pb2.ScenarioClientMessage()

        client_request_proto.sequence = self._next_sequence()

        client_request_proto.trafficRequest.list_flows_flag = self._list_flows_flag

        self.build_start_traffic_flows(
            client_request_proto.trafficRequest, eventdict['flow_on'])

        self.build_stop_traffic_flows(
            client_request_proto.trafficRequest, eventdict['flow_off'])

        self.build_emane_events(
            client_request_proto.emaneEvents, eventdict)

        self.build_jamming_events(
            client_request_proto.jammingEvents, eventdict)

        return client_request_proto.SerializeToString()


    def build_start_traffic_flows(self, trafficRequest, flow_on_events):
        for request in flow_on_events:
            request_proto = trafficRequest.startFlowRequests.add()

            request_proto.flow_name = request.flow_name

            for source in request.sources:
                request_proto.sources.append(source)

            for destination in request.destinations:
                request_proto.destinations.append(destination)

            request_proto.protocol_type = request.protocol.value
            request_proto.tos = int(request.tos)
            request_proto.ttl = int(request.ttl)
            request_proto.flow_type = emexscenario_pb2.SIMPLE
            request_proto.simple_flow.type = request.type.value
            request_proto.simple_flow.size_bytes = request.size_bytes
            request_proto.simple_flow.packet_rate = request.packet_rate
            request_proto.simple_flow.jitter_fraction = request.jitter_fraction


    def build_stop_traffic_flows(self, trafficRequest, flow_off_events):
        for request in flow_off_events:
            request_proto = trafficRequest.stopFlowRequests.add()

            request_proto.flow_name = request.flow_name

            for flow_id in request.flow_ids:
                request_proto.flow_ids.append(int(flow_id))

            for source in request.sources:
                request_proto.sources.append(source)

            for destination in request.destinations:
                request_proto.destinations.append(destination)


    def build_emane_events(self, emaneEvents, eventdict):
        """
         collate povs, pathlosses and antenna_pointings
         into a emexscenario EmaneEvent message, which
         are organized 1 per platform
        """
        evt_protos = {}

        for plt,pov in eventdict.get('pov', []):
            evt_proto = emaneEvents.add()
            evt_proto.platform_name = plt
            evt_protos[plt] = evt_proto

            pov_proto = evt_proto.pov.add()

            for component_name in pov.component_names:
                pov_proto.component_names.append(component_name)

            pov_proto.latitude = pov.latitude
            pov_proto.longitude = pov.longitude
            pov_proto.altitude = pov.altitude
            pov_proto.speed = pov.speed
            pov_proto.azimuth = pov.azimuth
            pov_proto.elevation = pov.elevation
            pov_proto.pitch = pov.pitch
            pov_proto.roll = pov.roll
            pov_proto.yaw = pov.yaw

        for plt,pathlosses in eventdict.get('pathloss', []):
            evt_proto = evt_protos.get(plt, None)

            if not evt_proto:
                evt_proto = emaneEvents.add()
                evt_proto.platform_name = plt
                evt_protos[plt] = evt_proto

            for pathloss in pathlosses:
                pathloss_proto = evt_proto.pathlosses.add()

                pathloss_proto.remote_platform_name = pathloss.remote_platform
                pathloss_proto.pathloss = pathloss.pathloss

                for component_name in pathloss.component_names:
                    pathloss_proto.component_names.append(component_name)

                for remote_component_name in pathloss.remote_component_names:
                    pathloss_proto.remote_component_names.append(remote_component_name)

        for plt,pointing in eventdict.get('antenna_pointing', []):
            evt_proto = evt_protos.get(plt, None)

            if not evt_proto:
                evt_proto = emaneEvents.add()
                evt_proto.platform_name = plt
                evt_protos[plt] = evt_proto

            pointing_proto = evt_proto.antenna_pointings.add()

            for component_name in pointing.component_names:
                pointing_proto.component_names.append(component_name)

            pointing_proto.azimuth = pointing.azimuth
            pointing_proto.elevation = pointing.elevation


    def build_jamming_events(self, jammingEvents, eventdict):
        """
        required Type type = 1;
        required string platform_name = 2;
        required float txpower = 3;
        required uint32 bandwidth = 4;
        required uint32 period = 5;
        required uint32 duty_cycle = 6;
        repeated uint64 frequencies = 7;
        """

        for jam_on_evt in eventdict.get('jam_on', []):
            print(type(jam_on_evt))
            print(jam_on_evt)
            jam_evt_proto = jammingEvents.add()

            jam_evt_proto.type = jam_evt_proto.JAM_ON

            jam_evt_proto.platform_name = jam_on_evt.platform_name

            for component_name in jam_on_evt.component_names:
                jam_evt_proto.component_names.append(component_name)

            jam_evt_proto.on.txpower = jam_on_evt.txpower
            jam_evt_proto.on.bandwidth = jam_on_evt.bandwidth
            jam_evt_proto.on.period = jam_on_evt.period
            jam_evt_proto.on.duty_cycle = jam_on_evt.duty_cycle

            for frequency in jam_on_evt.frequencies:
                jam_evt_proto.on.frequencies.append(frequency)


        for jam_off_evt in eventdict.get('jam_off', []):
            jam_evt_proto = jammingEvents.add()

            jam_evt_proto.type = jam_evt_proto.JAM_OFF

            jam_evt_proto.platform_name = jam_off_evt.platform_name

            for component_name in jam_off_evt.component_names:
                jam_evt_proto.component_names.append(component_name)



    def parse_server_reply(self, reply_str):
        reply = emexscenario_pb2.ScenarioServerMessage()

        reply.ParseFromString(reply_str)

        server_sequence = reply.sequence

        client_sequence = reply.client_sequence

        reply_message = None

        ok,message,flow_df = self._parse_traffic_reply(reply.trafficReply)

        logging.debug(f'received scenario server message '
                      f'client_sequence={client_sequence} '
                      f'server_sequence={server_sequence} '
                      f'ok={ok} '
                      f'message={message}')

        logging.debug(f'\n{flow_df}')

        return ok,message,flow_df


    def _parse_traffic_reply(self, trafficReply):
        bool_result = trafficReply.result == PASS

        rows = []

        for flowEntry in trafficReply.flowEntries:
            rows.append([flowEntry.flow_name,
                         flowEntry.active,
                         flowEntry.flow_id,
                         flowEntry.source,
                         flowEntry.destination,
                         flowEntry.tos,
                         flowEntry.ttl,
                         flowEntry.protocol_type,
                         flowEntry.simple_flow.type,
                         flowEntry.simple_flow.size_bytes,
                         flowEntry.simple_flow.packet_rate,
                         flowEntry.simple_flow.jitter_fraction])

        flow_df = DataFrame(rows, columns=['flow_name',
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


        return bool_result,trafficReply.message,flow_df
