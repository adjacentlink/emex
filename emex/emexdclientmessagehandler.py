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

import logging

from emex.antennatype import AntennaType
from emex.emoestate import EmoeState
from emex.platformtype import PlatformType
from emex.common_pb2 import PASS,FAIL
import emex.emexd_pb2 as emexd_pb2
from emex.emexdmessages import (
    ServiceAccessor,
    CheckEmoeReply,
    StartEmoeReply,
    StopEmoeReply,
    ListEmoesReply,
    ListEmoesReplyEntry,
    EmoeStateTransitionEvent
)


class EmexdClientMessageHandler:
    def __init__(self):
        pass


    def build_models_request_message(self):
        request = emexd_pb2.ClientMessage()

        request.type = request.MODEL_TYPES_REQUEST_TYPE

        return request.SerializeToString()


    def build_check_emoe_request_message(self, emoe):
        request = emexd_pb2.ClientMessage()

        request.type = request.CHECK_EMOE_REQUEST_TYPE

        request.checkEmoeRequest.emoe_name = emoe.name

        emoe.to_protobuf(request.checkEmoeRequest.emoe)

        return request.SerializeToString()


    def build_list_emoes_request_message(self):
        request = emexd_pb2.ClientMessage()

        request.type = request.LIST_EMOES_REQUEST_TYPE

        return request.SerializeToString()


    def build_start_emoe_request_message(self, emoe):
        request = emexd_pb2.ClientMessage()

        request.type = request.START_EMOE_REQUEST_TYPE

        request.startEmoeRequest.emoe_name = emoe.name

        emoe.to_protobuf(request.startEmoeRequest.emoe)

        return request.SerializeToString()


    def build_stop_emoe_request_message(self, emoe_handle):
        request = emexd_pb2.ClientMessage()

        request.type = request.STOP_EMOE_REQUEST_TYPE

        request.stopEmoeRequest.handle = emoe_handle

        return request.SerializeToString()


    def parse_models_reply_message(self, reply_str):
        reply = emexd_pb2.ServerMessage()

        reply.ParseFromString(reply_str)

        return self._build_models_reply_message(reply)

    def _build_models_reply_message(self, reply):
        antennatypes = {}

        platformtypes = {}

        if not reply.type == reply.MODEL_TYPES_REPLY_TYPE:
            raise ValueError(f'Unexpected reply type {reply.type}. Ignoring')

        for antennatype in reply.modelTypesReply.antennatypes:
            at = AntennaType.from_protobuf(antennatype)

            antennatypes[at.name] = at

        for platformtype in reply.modelTypesReply.platformtypes:
            pt = PlatformType.from_protobuf(platformtype)

            platformtypes[pt.name] = pt

        return antennatypes, platformtypes


    def parse_check_emoe_reply_message(self, reply_str):
        reply = emexd_pb2.ServerMessage()

        reply.ParseFromString(reply_str)

        return self._build_check_emoe_reply_message(reply)

    def _build_check_emoe_reply_message(self, reply):
        if not reply.type == reply.CHECK_EMOE_REPLY_TYPE:
            raise ValueError(f'Unexpected reply type {reply.type}.')

        return CheckEmoeReply(emoe_name = reply.checkEmoeReply.emoe_name,
                              result = reply.checkEmoeReply.result == PASS,
                              message = reply.checkEmoeReply.message)



    def parse_list_emoes_reply_message(self, reply_str):
        reply = emexd_pb2.ServerMessage()

        reply.ParseFromString(reply_str)

        return self._build_list_emoes_reply_message(reply)

    def _build_list_emoes_reply_message(self, reply):
        if not reply.type == reply.LIST_EMOES_REPLY_TYPE:
            raise ValueError(f'Unexpected reply type {reply.type}.')

        entries = []

        for entry in reply.listEmoesReply.entries:
            service_accessors = []

            for accessor in entry.emoe_accessors:
                service_accessors.append(ServiceAccessor(accessor.service_name,
                                                         accessor.ip_address,
                                                         accessor.port))

            entries.append(ListEmoesReplyEntry(entry.handle,
                                               entry.emoe_name,
                                               EmoeState(entry.state),
                                               entry.assigned_cpus,
                                               service_accessors))

        return ListEmoesReply(total_cpus = reply.listEmoesReply.total_cpus,
                              available_cpus = reply.listEmoesReply.available_cpus,
                              emoe_entries = entries)


    def parse_start_emoe_reply_message(self, reply_str):
        reply = emexd_pb2.ServerMessage()

        reply.ParseFromString(reply_str)

        return self._build_start_emoe_reply_message(reply)

    def _build_start_emoe_reply_message(self, reply):
        if not reply.type == reply.START_EMOE_REPLY_TYPE:
            raise ValueError(f'Unexpected reply type {reply.type}.')

        return StartEmoeReply(reply.startEmoeReply.emoe_name,
                              reply.startEmoeReply.result==PASS,
                              reply.startEmoeReply.message)


    def parse_stop_emoe_reply_message(self, reply_str):
        reply = emexd_pb2.ServerMessage()

        reply.ParseFromString(reply_str)

        return self._build_stop_emoe_reply_message(reply)

    def _build_stop_emoe_reply_message(self, reply):
        if not reply.type == reply.STOP_EMOE_REPLY_TYPE:
            raise ValueError(f'Unexpected reply type {reply.type}.')

        return StopEmoeReply(handle = reply.stopEmoeReply.handle,
                             emoe_name = reply.stopEmoeReply.emoe_name,
                             result = reply.stopEmoeReply.result==PASS,
                             message = reply.stopEmoeReply.message)


    def _build_emoe_state_transition_event_message(self, reply):
        if not reply.type == reply.EMOE_STATE_TRANSITION_EVENT:
            raise ValueError(f'Unexpected reply type {reply.type}.')

        service_accessors = []

        for accessor in reply.emoeStateTransitionEvent.emoe_accessors:
            service_accessors.append(ServiceAccessor(accessor.service_name,
                                                     accessor.ip_address,
                                                     accessor.port))

        return EmoeStateTransitionEvent(handle = reply.emoeStateTransitionEvent.handle,
                                        emoe_name = reply.emoeStateTransitionEvent.emoe_name,
                                        state = EmoeState(reply.emoeStateTransitionEvent.state),
                                        cpus = reply.emoeStateTransitionEvent.assigned_cpus,
                                        service_accessors = service_accessors,
                                        message = reply.emoeStateTransitionEvent.message)



    def parse_reply(self, reply_str):
        reply = emexd_pb2.ServerMessage()

        reply.ParseFromString(reply_str)

        if reply.type == reply.MODEL_TYPES_REPLY_TYPE:
            return self._build_models_reply_message(reply)
        elif reply.type == reply.CHECK_EMOE_REPLY_TYPE:
            return self._build_check_emoe_reply_message(reply)
        elif reply.type == reply.LIST_EMOES_REPLY_TYPE:
            return self._build_list_emoes_reply_message(reply)
        elif reply.type == reply.START_EMOE_REPLY_TYPE:
            return self._build_start_emoe_reply_message(reply)
        elif reply.type == reply.STOP_EMOE_REPLY_TYPE:
            return self._build_stop_emoe_reply_message(reply)
        elif reply.type == reply.EMOE_STATE_TRANSITION_EVENT:
            return self._build_emoe_state_transition_event_message(reply)

        return None
