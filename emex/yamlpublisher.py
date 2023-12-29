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


class YamlPublisher:
    def __init__(self, args):
        scenario_rpc = ScenarioRpcClient(args.eventservicegroup)

        if not len(toks) == 2:
            print('eventservicegroup must be in form address:port')
            exit(1)

        mcgroup,port = toks

        service = None

        try:
            service = EventService((mcgroup, int(port), args.eventservicedevice))

        except EventServiceException as e:
            print(e, file=sys.stderr)
            exit(1)

        self._service = service


    def publish_locations(self, current_state):
        event = LocationEvent()

        for nodeid,loc in current_state.iterrows():
            event.append(nodeid,
                         latitude=loc.lat,
                         longitude=loc.lon,
                         altitude=loc.alt,
                         azimuth=loc.az,
                         elevation=loc.el,
                         magnitude=loc.speed,
                         pitch=loc.pitch,
                         roll=loc.roll,
                         yaw=loc.yaw)

        self._service.publish(0, event)


    def publish_antenna_profiles(self, current_state):
        event = AntennaProfileEvent()

        for nodeid, pnt in current_state.iterrows():
            event.append(nemId=nodeid, profile=int(pnt.ant_num), azimuth=pnt.az, elevation=pnt.el)

        self._service.publish(0, event)


    def publish_pathlosses(self, current_state):
        pathloss_events = defaultdict(lambda: PathlossEvent())

        for (nodeid1, nodeid2), row in current_state.iterrows():
            pathloss_events[nodeid2].append(nodeid1, forward=row.pathloss)

        for nodeid2, event in pathloss_events.items():
            self._service.publish(nodeid2, event)
