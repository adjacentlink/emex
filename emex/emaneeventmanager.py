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

from collections import defaultdict
import logging

from emane.events import EventService,LocationEvent,PathlossEvent,AntennaProfileEvent

from emex.emoemessages import SimpleTrafficFlowType,TrafficProtocolType


class EmaneEventManager:
    def __init__(self, nemid_map, antenna_profileid_map):
        self._service = None

        self._nemid_map = nemid_map

        self._antenna_profileid_map = antenna_profileid_map


    def send_events(self, emane_events):
        if not self._service:
            try:
                self._service = EventService(('224.1.2.8', 45703, 'backchan0'))
            except:
                message = 'failed to open emane EventService'

                logging.error(message)

                return False,message

        ok,message = self._send_pov_events(self._service, emane_events)
        if not ok:
            return ok,message

        ok,message = self._send_pathloss_events(self._service, emane_events)
        if not ok:
            return ok,message

        ok,message = self._send_antenna_pointing_events(self._service, emane_events)
        if not ok:
            return ok,message

        return True,''


    def _send_pov_events(self, service, emane_events):
        for plt_name,povs in emane_events.get('povs',{}).items():
            pov_event = LocationEvent()

            for pov in povs:
                nemids = []

                if pov.component_names:
                    for c_name in pov.component_names:
                        nemids.append(self._nemid_map[(plt_name, c_name)])
                else:
                    nemids = [nemid
                              for (plt_name2,_),nemid in self._nemid_map.items()
                              if plt_name == plt_name2]

                for nemid in nemids:
                    pov_event.append(
                        nemid,
                        latitude=pov.latitude,
                        longitude=pov.longitude,
                        altitude=pov.altitude,
                        magnitude=pov.speed,
                        azimuth=pov.azimuth,
                        elevation=pov.elevation,
                        pitch=pov.pitch,
                        roll=pov.roll,
                        yaw=pov.yaw)

                logging.debug(f'emane_event pov '
                              f'{plt_name} '
                              f'nem:{nemid} '
                              f'lat:{pov.latitude} '
                              f'lon:{pov.longitude} '
                              f'alt:{pov.altitude} '
                              f'speed:{pov.speed} '
                              f'az:{pov.azimuth} '
                              f'el:{pov.elevation} '
                              f'pitch:{pov.pitch} '
                              f'roll:{pov.roll} '
                              f'yaw:{pov.yaw}')

            service.publish(0, pov_event)

        return True,''


    def _send_pathloss_events(self, service, emane_events):
        pathloss_events = defaultdict(lambda: PathlossEvent())

        for plt_name,pathlosses in emane_events.get('pathlosses',{}).items():
            for pathloss in pathlosses:
                remote_plt_name = pathloss.remote_platform

                local_nemids = []
                if pathloss.component_names:
                    for c_name in pathloss.component_names:
                        local_nemids.append(self._nemid_map[(plt_name, c_name)])
                else:
                    local_nemids = [nemid
                                    for (plt_name2,_),nemid in self._nemid_map.items()
                                    if plt_name == plt_name2]

                remote_nemids = []
                if pathloss.remote_component_names:
                    for rc_name in pathloss.remote_component_names:
                        remote_nemids.append(self._nemid_map[(remote_plt_name, rc_name)])
                else:
                    remote_nemids = [nemid
                                     for (remote_plt_name2,_),nemid in self._nemid_map.items()
                                     if remote_plt_name == remote_plt_name2]

                for nemid1 in local_nemids:
                    for nemid2 in remote_nemids:
                        pathloss_events[nemid1].append(nemid2,
                                                       forward=pathloss.pathloss)
                        pathloss_events[nemid2].append(nemid1,
                                                       forward=pathloss.pathloss)

                        logging.debug(
                            f'emane_event pathloss '
                            f'{plt_name} '
                            f'nem1:{nemid1} '
                            f'nem2:{nemid2} '
                            f'pathloss:{pathloss.pathloss}')

        for nemid,pathloss_event in pathloss_events.items():
            service.publish(nemid, pathloss_event)

        return True,''


    def _send_antenna_pointing_events(self, service, emane_events):
        antenna_pointing_dict = emane_events.get('antenna_pointings',{})

        if antenna_pointing_dict:
            antenna_pointing_event = AntennaProfileEvent()

            for plt_name,pointings in antenna_pointing_dict.items():
                for pointing in pointings:
                    profileids = []

                    nemids = []

                    if pointing.component_names:
                        for component_name in pointing_component_names:
                            profileids.append(
                                self._antenna_profileid_map[(plt_name,component_name)])

                            nemids.append(
                                self._nemid_map[(plt_name,component_name)])
                    else:
                        # if component_names is not specified, it applies to
                        # all of the platforms antennas
                        for (plt_name2,component_name),profileid in self._antenna_profileid_map.items():
                            if plt_name == plt_name2:
                                profileids.append(profileid)

                                nemids.append(
                                    self._nemid_map[(plt_name,component_name)])

                    for profileid,nemid in zip(profileids,nemids):
                        logging.debug(
                            f'emane_event antenna_profile '
                            f'{plt_name} '
                            f'nem:{nemid} '
                            f'profileid:{profileid} '
                            f'az:{pointing.azimuth} '
                            f'el:{pointing.elevation}')

                        antenna_pointing_event.append(nemId=nemid,
                                                      profile=profileid,
                                                      azimuth=pointing.azimuth,
                                                      elevation=pointing.elevation)

            service.publish(0, antenna_pointing_event)

        return True,''
