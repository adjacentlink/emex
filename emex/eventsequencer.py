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

import datetime
import math
import time


class EventSequencerIterator(object):
    def __init__(self, events, starttime):
        self._events = sorted(events.items())
        self._starttime = starttime
        self._index = 0

    def next(self):
        return self.__next__()

    def __next__(self):
        if self._index >= len(self._events):
            raise StopIteration
        else:
            eventtime,eventlist = self._events[self._index]
            self._index += 1
            self._wait(eventtime, self._starttime)
            return eventtime,eventlist

    def _wait(self, eventtime, starttime):
        if math.isinf(eventtime) and eventtime < 0:
            return

        nowtime = datetime.datetime.now()
        eventabstime = starttime + datetime.timedelta(seconds=eventtime)
        sleeptime = (eventabstime - nowtime).total_seconds()
        if sleeptime <= 0:
            return
        time.sleep(sleeptime)


class EventSequencer:
    def __init__(self, events):
        self._events = events

    @property
    def num_events(self):
        return len(self._events)

    def __iter__(self):
        return EventSequencerIterator(self._events, datetime.datetime.now())
