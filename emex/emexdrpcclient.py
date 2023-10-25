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

import socket
import struct

from emex.emexdclientmessagehandler import EmexdClientMessageHandler


class EmexdRpcClient:
    """Remote Procedure Call (RPC) emexd Client.

    A simple client that enforces remote procedure call EMEX API
    (emex.proto) interactions with emexd (the EMEX daemon) by sending
    requests and waiting for replies. It does not expect and will not
    properly handle asynchronous EmoeStateTransitionEvent messages
    from the daemon - therefore it can only be used with a daemon
    running with the parameter "state-messages" set to False.

    The client may, nonetheless query the daemon for current Emoe
    status via the ListEmoesRequest/ListEmoesReply exchange
    (listemoes) call.
    """
    def __init__(self, endpoint=('127.0.0.1', 49901)):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self._socket.connect(endpoint)

        self._message_handler = EmexdClientMessageHandler()


    def close(self):
        self._socket.close()


    def getmodels(self):
        reply_str = self._send_and_wait(
            self._message_handler.build_models_request_message())

        return self._message_handler.parse_models_reply_message(reply_str)


    def checkemoe(self, emoe):
        reply_str = self._send_and_wait(
            self._message_handler.build_check_emoe_request_message(emoe))

        return self._message_handler.parse_check_emoe_reply_message(reply_str)


    def listemoes(self):
        reply_str = self._send_and_wait(
            self._message_handler.build_list_emoes_request_message())

        return self._message_handler.parse_list_emoes_reply_message(reply_str)


    def startemoe(self, emoe):
        reply_str = self._send_and_wait(
            self._message_handler.build_start_emoe_request_message(emoe))

        return self._message_handler.parse_start_emoe_reply_message(reply_str)


    def stopemoe(self, emoe_handle):
        reply_str = self._send_and_wait(
            self._message_handler.build_stop_emoe_request_message(emoe_handle))

        return self._message_handler.parse_stop_emoe_reply_message(reply_str)


    def _send_and_wait(self, request_str):
        format_str = '!I%ds' % len(request_str)

        bufstr = struct.pack(format_str, len(request_str), request_str)

        self._socket.send(bufstr)

        (count,) = struct.unpack('!I', self._socket.recv(4))

        return struct.unpack('%ds' % count, self._socket.recv(count, socket.MSG_WAITALL))[0]
