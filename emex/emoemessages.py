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


import enum
from collections import namedtuple

import emex.emexscenario_pb2 as emexscenario_pb2


class TrafficProtocolType(enum.IntEnum):
    UDP = emexscenario_pb2.UDP
    TCP = emexscenario_pb2.TCP
    MULTICAST = emexscenario_pb2.MULTICAST


class TrafficFlowType(enum.IntEnum):
    SIMPLE = emexscenario_pb2.SIMPLE


class SimpleTrafficFlowType(enum.IntEnum):
    PERIODIC = emexscenario_pb2.SimpleFlow.PERIODIC
    POISSON = emexscenario_pb2.SimpleFlow.POISSON
    JITTER = emexscenario_pb2.SimpleFlow.JITTER


StartSimpleFlowRequest = \
    namedtuple('StartSimpleFlowRequest',
               ['flow_name','sources','destinations',
                'protocol','tos','ttl',
                'type','size_bytes','packet_rate','jitter_fraction'])


StopFlowRequest = \
    namedtuple('StopFlowRequest',
               ['flow_name','flow_ids', 'sources','destinations'])


JamOnEvent = \
    namedtuple('JamOnEvent',
               ['platform_name', 'component_names',
                'txpower', 'bandwidth',
                'period', 'duty_cycle',
                'frequencies'])

JamOffEvent = \
    namedtuple('JamOffEvent',
               ['platform_name', 'component_names'])

