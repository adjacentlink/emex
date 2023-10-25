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

from emex.common_pb2 import PASS,FAIL
import emex.emexscenario_pb2 as emexscenario_pb2
from emex.emoemessages import SimpleTrafficFlowType,StartSimpleFlowRequest,StopFlowRequest,TrafficProtocolType,JamOnEvent,JamOffEvent
from emex.emaneeventmessages import POV,Pathloss,AntennaPointing


class ScenarioServerMessageHandler:
    def __init__(self):
        self._send_sequence = 0


    def _next_sequence(self):
        self._send_sequence += 1
        return self._send_sequence


    def parse_client_request(self, request_str):
        request = emexscenario_pb2.ScenarioClientMessage()

        request.ParseFromString(request_str)

        client_sequence = request.sequence

        requests = self._parse_traffic_request(request.trafficRequest)

        requests.update(self._parse_emane_events(request.emaneEvents))

        requests.update(self._parse_jamming_events(request.jammingEvents))

        return client_sequence,requests


    def _parse_traffic_request(self, trafficRequest):
        requests = defaultdict(lambda: [])

        requests['flow_on'] = \
            self._parse_start_flow_requests(trafficRequest.startFlowRequests)

        requests['flow_off'] = \
            self._parse_stop_flow_requests(trafficRequest.stopFlowRequests)

        requests['list_flows_flag'] = trafficRequest.list_flows_flag

        return requests


    def _parse_start_flow_requests(self, startFlowRequests):
        start_flow_requests = []

        for request in startFlowRequests:
            flow_name = request.flow_name

            sources = list(request.sources)

            destinations = list(request.destinations)

            protocol = TrafficProtocolType(request.protocol_type)

            tos = request.tos

            ttl = request.ttl

            flow_type = request.flow_type

            if flow_type == emexscenario_pb2.SIMPLE:
                simple_flow_type = SimpleTrafficFlowType(request.simple_flow.type)

                size_bytes = request.simple_flow.size_bytes

                packet_rate = request.simple_flow.packet_rate

                jitter_fraction = request.simple_flow.jitter_fraction

                start_flow_requests.append(
                    StartSimpleFlowRequest(flow_name, sources, destinations,
                                           protocol, tos, ttl,
                                           simple_flow_type,
                                           size_bytes, packet_rate, jitter_fraction))
            else:
                logging.error('Unknown flow type request')

        return tuple(start_flow_requests)


    def _parse_stop_flow_requests(self, stopFlowRequests):
        stop_flow_requests = []

        for request in stopFlowRequests:
            flow_name = request.flow_name

            flow_ids = list(request.flow_ids)

            sources = list(request.sources)

            destinations = list(request.destinations)

            stop_flow_requests.append(
                StopFlowRequest(flow_name, flow_ids, sources, destinations))

        return tuple(stop_flow_requests)


    def _parse_emane_events(self, emaneEvents):
        povs = defaultdict(lambda:[])
        pathlosses = defaultdict(lambda:[])
        antenna_pointings = defaultdict(lambda:[])

        for event_proto in emaneEvents:
            plt = event_proto.platform_name

            for pov_proto in event_proto.pov:
                povs[plt].append(
                    POV(component_names = pov_proto.component_names,
                        latitude = pov_proto.latitude,
                        longitude = pov_proto.longitude,
                        altitude = pov_proto.altitude,
                        speed = pov_proto.speed,
                        azimuth = pov_proto.azimuth,
                        elevation = pov_proto.elevation,
                        pitch = pov_proto.pitch,
                        roll = pov_proto.roll,
                        yaw = pov_proto.yaw))

            for pathloss_proto in event_proto.pathlosses:
                pathlosses[plt].append(
                    Pathloss(component_names=pathloss_proto.component_names,
                             remote_platform=pathloss_proto.remote_platform_name,
                             remote_component_names=pathloss_proto.remote_component_names,
                             pathloss=pathloss_proto.pathloss))

            for antenna_pointing_proto in event_proto.antenna_pointings:
                antenna_pointings[plt].append(
                    AntennaPointing(
                        component_names=antenna_pointing_proto.component_names,
                        azimuth=antenna_pointing_proto.azimuth,
                        elevation=antenna_pointing_proto.elevation))

        events = {
            'povs':povs,
            'pathlosses':pathlosses,
            'antenna_pointings':antenna_pointings
        }

        return {'emane_events': events}


    def _parse_jamming_events(self, jammingEvents):
        events = []

        for jam_evt_proto in jammingEvents:
            if jam_evt_proto.type == emexscenario_pb2.JammingEvent.JAM_ON:
                events.append(
                    JamOnEvent(jam_evt_proto.platform_name,
                               jam_evt_proto.component_names,
                               jam_evt_proto.on.txpower,
                               jam_evt_proto.on.bandwidth,
                               jam_evt_proto.on.period,
                               jam_evt_proto.on.duty_cycle,
                               jam_evt_proto.on.frequencies))
            else:
                events.append(
                    JamOffEvent(jam_evt_proto.platform_name,
                               jam_evt_proto.component_names))

        return {'jamming_events': events}


    def build_result(self, client_sequence, ok, message, flows_df):
        reply = emexscenario_pb2.ScenarioServerMessage()

        reply.sequence = self._next_sequence()

        reply.client_sequence = client_sequence

        logging.info(f'build_traffic_result '
                     f'sequence={reply.sequence} ',
                     f'client_sequence={client_sequence} ',
                     f'ok={ok} '
                     f'message={message}')

        reply.trafficReply.result = PASS if ok else FAIL

        reply.trafficReply.message = message

        self._add_traffic_flow_entries(reply.trafficReply, flows_df)

        reply_str = reply.SerializeToString()

        return reply_str


    def _add_traffic_flow_entries(self, trafficReply, flows_df):
        for _,row in flows_df.iterrows():
            flowEntry = trafficReply.flowEntries.add()

            flowEntry.flow_name = row.flow_name
            flowEntry.active = row.active
            flowEntry.flow_id = row.flow_id
            flowEntry.source = row.source
            flowEntry.destination = row.destination
            flowEntry.tos = row.tos
            flowEntry.ttl = row.ttl
            flowEntry.protocol_type = row.proto
            flowEntry.flow_type = emexscenario_pb2.SIMPLE
            flowEntry.simple_flow.type = row.flow_pattern
            flowEntry.simple_flow.size_bytes = row.size_bytes
            flowEntry.simple_flow.packet_rate = row.packet_rate
            flowEntry.simple_flow.jitter_fraction = row.jitter_fraction
