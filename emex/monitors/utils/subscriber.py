# Copyright (c) 2023 - Adjacent Link LLC, Bridgewater, New Jersey
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
import struct
import threading
import traceback
import zmq

import otestpoint.interface.probereport_pb2
from emex.monitors.utils.protoparsers import parse_proto,aggregate


class Subscriber:
    def __init__(self, endpoint, tag_map, relative_timestamp=False):
        self._endpoint = endpoint

        self._tag_map = tag_map

        self._relative_timestamp = relative_timestamp

        self._cancel_event = threading.Event()

        context = zmq.Context()

        self._zmq_subscriber = context.socket(zmq.SUB)

        self._zmq_subscriber.setsockopt(zmq.IPV4ONLY,0)

        self._endpoint = "tcp://%s" % endpoint
        self._zmq_subscriber.connect(self._endpoint)

        self._zmq_subscriber.setsockopt(zmq.SUBSCRIBE, b'')

        self._poller = zmq.Poller()

        self._poller.register(self._zmq_subscriber, zmq.POLLIN)

        self._zero_timestamp = 0
        self._last_timestamp = None

        self._timestamp_dfs = []

        self._thread = None


    def stop(self):
        self._cancel_event.set()
        logging.info('stop')


    def run(self, handler, timeout=10):
        self._thread = threading.Thread(target=self.do_run, args=(handler, timeout))

        self._thread.setDaemon(True)

        self._thread.start()

        self._thread.join()


    def do_run(self, handler, timeout=None):
        try:
            while not self._cancel_event.is_set():
                socks = dict(self._poller.poll(timeout))

                if (self._zmq_subscriber in socks and socks[self._zmq_subscriber] == zmq.POLLIN):
                    # receive and parse the next probe report
                    msgs = self._zmq_subscriber.recv_multipart()

                    report_proto = otestpoint.interface.probereport_pb2.ProbeReport()

                    report_proto.ParseFromString(msgs[1])

                    dfs = parse_proto(report_proto, self._tag_map)

                    if not self._zero_timestamp and self._relative_timestamp:
                        # capture the first timestamp to use to subtract from the
                        # reported timestamps if we want scenario relative timestamps
                        # in the dfs
                        self._zero_timestamp = int(report_proto.timestamp)

                    # collect all of the reports belonging to the same timestamp
                    # and aggregate and return them when the next timestamp comes in
                    if self._last_timestamp and not report_proto.timestamp == self._last_timestamp:
                        aggregated_dfs = aggregate(self._timestamp_dfs, self._zero_timestamp)
                        self._timestamp_dfs.clear()

                        timestamp = self._last_timestamp-self._zero_timestamp
                        self._last_timestamp = report_proto.timestamp
                        self._timestamp_dfs.extend(dfs)

                        handler(timestamp, aggregated_dfs)
                    else:
                        self._last_timestamp = report_proto.timestamp
                        self._timestamp_dfs.extend(dfs)

        except KeyboardInterrupt:
            print(traceback.format_exc())
