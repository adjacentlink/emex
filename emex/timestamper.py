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

import datetime
import os
import socket
import time


class Timestamp:
    def __init__(self, timestamp, emex_workdir):
        self._timestamp = timestamp
        self._emex_workdir = emex_workdir


    @property
    def timestamp(self):
        return self._timestamp


    @property
    def emoe_id(self):
        t = datetime.datetime.fromtimestamp(self.timestamp)

        return  '%s.%04d%02d%02dT%02d%02d%02d' % (socket.gethostname(),
                                                  t.year,
                                                  t.month,
                                                  t.day,
                                                  t.hour,
                                                  t.minute,
                                                  t.second)

    def workdir(self, tag):
        return os.path.join(self._emex_workdir, f'{self.emoe_id}.{tag}')


    def mcast_address(self):
        ts = int(self.timestamp)

        octet1 = 239

        octet2 = ts // 256 // 256 % 256

        octet3 = ts // 256 % 256

        octet4 = ts % 256

        return f'{octet1}.{octet2}.{octet3}.{octet4}'



class Timestamper:
    EMEX_WORKDIR = '/tmp/emex'

    def __init__(self, emex_workdir=EMEX_WORKDIR):
        self._last_timestamp = 0
        self._emex_workdir = emex_workdir


    @property
    def next_timestamp(self):
        next_timestamp = time.time()

        # enforce timestamps are strictly increasing
        next_timestamp = max(self._last_timestamp + 1, next_timestamp)

        self._last_timestamp = next_timestamp

        return Timestamp(next_timestamp, self._emex_workdir)
