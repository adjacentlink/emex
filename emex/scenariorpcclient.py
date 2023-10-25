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
import socket
import struct

from emex.utils import sock_send_string,sock_recv_string
from emex.scenarioclientmessagehandler import ScenarioClientMessageHandler


class ScenarioRpcClient:
    """Remote Procedure Call (RPC) EMOE Scenario Client.

    A simple client that enforces remote procedure call EMEX Scenario
    API (emexscenario.proto) interactions with a running EMOE. The
    remote endpoint is the emexcontainerd instance running within the
    target EMOE. It's service endpoint is exposed as the 'emexcontainerd'
    accessor that is advertised in teh startScenarioReply EMEX message
    from the serving emexd.
    """
    def __init__(self, endpoint, list_flows_flag=True):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        logging.info(f'Connecting to emoe at {endpoint}')

        self._socket.connect(endpoint)

        self._message_handler = ScenarioClientMessageHandler(list_flows_flag)


    def close(self):
        self._socket.close()


    def getsockname(self):
        if self._socket:
            return self._socket.getsockname()
        return None


    def send_event(self, eventdict):
        reply_str = self._send_and_wait(
            self._message_handler.build_client_message(eventdict))

        return self._message_handler.parse_server_reply(reply_str)


    def _send_and_wait(self, request_str):
        sock_send_string(self._socket, request_str)

        return sock_recv_string(self._socket)

