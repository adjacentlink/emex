#
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

from collections import defaultdict

from emex.scenariorpcclient import ScenarioRpcClient
from emex.emaneeventmessages import POV,Pathloss,AntennaPointing


class ScenarioPublisher:
    def __init__(self, emoe_endpoint):
        self._client = ScenarioRpcClient(emoe_endpoint)


    def publish_locations(self, current_state):
        events = []

        for (nodeid,node),loc in current_state.iterrows(full_index=True):
            events.append((node,POV([],
                                    loc.lat,loc.lon,loc.alt,
                                    loc.speed,loc.az,loc.el,
                                    loc.pitch,loc.roll,loc.yaw)))

        self._client.send_event({'pov':events})


    def publish_antenna_profiles(self, current_state):
        events = []

        for (nodeid,node),pointing in current_state.iterrows(full_index=True):
            events.append((node,AntennaPointing([],pointing.az,pointing.el)))

        self._client.send_event({'antenna_pointing':events})


    def publish_pathlosses(self, current_state):
        events = defaultdict(lambda: [])

        for (node1id,nodeid2),p in current_state.iterrows():
            events[p.node1].append(Pathloss(p.node2, p.pathloss, [], []))

        self._client.send_event({
            'pathloss':[
                (node,pathlosses)
                for node,pathlosses in events.items()
            ]})
