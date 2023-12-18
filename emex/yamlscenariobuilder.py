# Copyright (c) 2022,2023 - Adjacent Link LLC, Bridgewater, New Jersey
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
import re
import sys
from yaml import safe_load

from emex.initialcondition import InitialCondition
from emex.emaneeventmessages import POV,AntennaPointing,Pathloss
from emex.emoeerror import EmoeError
from emex.antenna import Antenna
from emex.platform import Platform
from emex.emoemessages import (
    TrafficProtocolType,
    TrafficFlowType,
    SimpleTrafficFlowType,
    StartSimpleFlowRequest,
    StopFlowRequest,
    JamOnEvent,
    JamOffEvent
)

class YamlScenarioBuilder:
    def __init__(self, emex_yaml_file):
        contents = safe_load(open(emex_yaml_file))

        self._name = contents['name']

        self._description = contents.get('description', self._name)

        self._emoe_dict = contents['emoe']

        self._platform_names = self._emoe_dict['platforms'].keys()

        self._event_parsers = {
            'flow_on': self._parse_flow_on,
            'flow_off': self._parse_flow_off,
            'end': self._parse_end,
            'pov': self._parse_pov,
            'pathloss': self._parse_pathloss,
            'antenna_pointing': self._parse_antenna_pointing,
            'jam_on': self._parse_jam_on,
            'jam_off': self._parse_jam_off
        }

        self._events = self._parse_events(contents['scenario'])


    @property
    def name(self):
        return self._name


    @property
    def emoe_dict(self):
        return self._emoe_dict


    def build(self, platform_types, antenna_types):
        platforms = self.build_platforms(platform_types)

        antennas = self.build_antennas(antenna_types)

        initial_conditions = self._build_initial_conditions()

        return (
            platforms,
            antennas,
            initial_conditions
        )


    def build_platforms(self, platformtypes):
        platforms = []

        for plt_name,plt_config in self._emoe_dict['platforms'].items():
            config_platform_type = plt_config['type']

            component_labels = defaultdict(lambda: [])

            labels = plt_config.get('labels', None)

            if labels:
                for c_name,label in [tok.strip().split('.') for tok in labels.split()]:
                    component_labels[c_name].append(label)


            platform_type = platformtypes.get(config_platform_type, None)

            if not platform_type:
                raise EmoeError(f'Unknown type "{config_platform_type}" '
                                f'for platform "{plt_name}".')
            """
            config = {
            'r1': {
                  'rm': {
                        'participantid':1
                  }
            }
            """
            parameters = plt_config.get('parameters', {})

            if parameters is None:
                parameters = {}

            config = defaultdict(lambda: defaultdict(lambda: {}))
            for component_group_param,vals in parameters.items():
                c_name,pg_name,p_name = component_group_param.split('.')

                config[c_name][pg_name][p_name] = vals

            logging.debug(config)

            platform = Platform(plt_name,
                                platform_type,
                                user_config=config,
                                labels=component_labels)


            platforms.append(platform)

        return platforms


    def build_antennas(self, antennatypes):
        antenna_configs = self._emoe_dict.get('antennas', {})

        antennas = []

        for antennaname,config in antenna_configs.items():
            antennatype = config['type']

            if not antennatype in antennatypes:
                print(f'"{antennatype}" not found in available antenna types. Ignoring.',
                      file=sys.stderr)
                return

            user_config = defaultdict(lambda: [])

            if config.get('parameters'):
                for param_name,value in config.get('parameters', {}).items():
                    user_config[param_name] = value

            antennas.append(Antenna(antennaname,
                                    antennatypes[antennatype],
                                    user_config))

        return antennas


    @property
    def events(self):
        return self._events


    def _build_initial_conditions(self):
        """
        Returns:
            a list of InitialCondition objects
        """

        initial_conditions_dict = self._emoe_dict.get('initial_conditions', {})
        """
        emoe:
            platforms:

                ...

            initial_conditions: <-- initial_conditions_dict
                pov: |
                    rfpipe-001  37.005 -109.050 3.0
                    rfpipe-002  37.005 -109.040 3.0
                    rfpipe-003  36.995 -109.040 3.0
                    rfpipe-004  36.995 -109.050 3.0
                    sensor-001  37.000 -109.045 3.0
                pathloss: |
                    rfpipe-001  rfpipe-002:90 rfpipe-003:120 rfpipe-004:90  sensor-001:80
                    rfpipe-002                rfpipe-003:90  rfpipe-004:120 sensor-001:80
                    rfpipe-003                               rfpipe-004:90  sensor-001:80
                    rfpipe-004                                              sensor-001:80
                antenna_pointing: |
                    rfpipe-001  90.0 0.0
                    rfpipe-003   0.0 0.0
                    rfpipe-004  45.0 0.0
        """
        if not initial_conditions_dict:
            return {}

        # first build initial POVs
        povs = self._unpack_povs(initial_conditions_dict)

        # then initial Pathlosses
        pathlosses = self._unpack_pathlosses(initial_conditions_dict)

        # and antenna pointings
        antenna_pointings = \
            self._unpack_antenna_pointings(initial_conditions_dict)

        # collect together and build an initial condition
        # for each named platform
        all_names = sorted(
            set(list(povs.keys()) + \
                list(pathlosses.keys()) +
                list(antenna_pointings.keys())))

        initial_conditions = []

        for plt_name in all_names:
            initial_conditions.append(
                InitialCondition(plt_name,
                                 povs.get(plt_name,None),
                                 pathlosses.get(plt_name,[]),
                                 antenna_pointings.get(plt_name,[])))

        return initial_conditions


    def _parse_platform_components(self, tok):
        plt_cmp = tok.split('.')

        plt_name = plt_cmp[0]

        cmp_names = [plt_cmp[1]] if len(plt_cmp)>1 else []

        return plt_name,cmp_names


    def _parse_events(self, scenario_dict):
        events = defaultdict(lambda: defaultdict(lambda:[]))

        for time,multi_line in scenario_dict.items():
            lines = multi_line.split('\n')

            for line in lines:
                line = line.strip()

                if not line:
                    continue

                tokens = line.split()

                eventtype = tokens[0]

                events[time][eventtype].append(
                    self._event_parsers[eventtype](tokens[1:]))

        return events


    def _parse_flow_on(self, tokens):
        # flow_on source=lteue* destination=lteepc-001 periodic 1024 10.0
        # flow_on source=lteepc-001 destination=lteue* periodic 1024 10.0

        flow_name = ''

        source_regx = '.*'

        destination_regx = '.*'

        protocol = TrafficProtocolType.UDP

        tos = 0

        ttl = 1

        subtoks = list(map(lambda s: s.split('='), tokens))

        subtoks.reverse()

        while len(subtoks[-1]) == 2:
            tname,tval = subtoks.pop()

            tname = tname.lower()
            logging.debug(f'tname={tname} tval={tval}')

            if tname == 'name':
                flow_name = tval

            elif tname == 'source':
                source_regx = tval

            elif tname == 'destination':
                destination_regx = tval

            elif tname == 'proto':
                protocol = {
                    'udp':TrafficProtocolType.UDP,
                    'tcp':TrafficProtocolType.TCP,
                    'multicast':TrafficProtocolType.MULTICAST
                }.get(tval.lower(), None)

                if not protocol:
                    raise ValueError(f'unknown flow_on protocol "{protocol}"')

            elif tname == 'tos':
                tos = tval

            elif tname == 'ttl':
                ttl = tval

            else:
                raise ValueError(f'unknown flow_on specifier "{tname}"')

        flowtypetok = subtoks.pop()[0]

        flowtype = {
            'periodic': SimpleTrafficFlowType.PERIODIC,
            'poisson': SimpleTrafficFlowType.POISSON,
            'jitter': SimpleTrafficFlowType.JITTER
        }.get(flowtypetok, None)

        if flowtype is None:
            raise ValueError(f'unknown flow_on flow type "{flowtypetok}"')

        packet_rate = float(subtoks.pop()[0])

        size_bytes = int(subtoks.pop()[0])

        jitter_fraction = 0.0

        if subtoks:
            jitter_fraction = float(subtoks.pop()[0])

        sources = []
        if source_regx:
            sources = [source for source in self._platform_names
                       if re.match(source_regx, source)]

        if source_regx and not sources:
            raise ValueError(f'Flow source {source_regx} does not match '
                             f'any platform name, quitting.')

        destinations = []
        if destination_regx:
            destinations = [destination for destination in self._platform_names
                            if re.match(destination_regx, destination)]

        if destination_regx and not destinations:
            raise ValueError(f'Flow destination {destination_regx} does not match '
                             f'any platform name, quitting.')

        return StartSimpleFlowRequest(flow_name,
                                      sources,
                                      destinations,
                                      protocol,
                                      tos,
                                      ttl,
                                      flowtype,
                                      size_bytes,
                                      packet_rate,
                                      jitter_fraction)


    def _parse_flow_off(self, tokens):
        flow_name = ''

        flow_ids = []

        source_regx = '.*'

        destination_regx = '.*'

        subtoks = list(map(lambda s: s.split('='), tokens))

        subtoks.reverse()

        while subtoks and len(subtoks[-1]) == 2:
            tname,tval = subtoks.pop()

            tname = tname.lower()
            logging.debug(f'tname={tname} tval={tval}')

            if tname == 'name':
                flow_name = tval
            elif tname == 'flow_id':
                flow_ids.append(tval)
            elif tname == 'source':
                source_regx = tval
            elif tname == 'destination':
                destination_regx = tval
            else:
                raise ValueError(f'unknown flow_on specifier "{tname}"')

        sources = []
        if source_regx:
            sources = [source for source in self._platform_names
                       if re.match(source_regx, source)]

        if source_regx and not sources:
            raise ValueError(f'Flow source {source_regx} does not match '
                             f'any platform name, quitting.')

        destinations = []

        if destination_regx:
            destinations = [destination for destination in self._platform_names
                            if re.match(destination_regx, destination)]

        if destination_regx and not destinations:
            raise ValueError(f'Flow destination {destination_regx} does not match '
                             f'any platform name, quitting.')

        return StopFlowRequest(flow_name, flow_ids, sources, destinations)


    def _unpack_povs(self, initial_conditions_dict):
        povs = {}

        pov_lines = \
            list(filter(lambda x: len(x.strip())>0,
                        initial_conditions_dict.get('pov', '').split('\n')))

        for line in pov_lines:
            plt_name,pov = self._parse_pov(line.split())

            if plt_name in povs:
                logging.warning(f'found duplicate pov values '
                                f'for platform {plt_name}')

            povs[plt_name] = pov

        return povs


    def _parse_pov(self, tokens):
        """
            rfpipe-001  37.005 -109.050 3.0
            rfpipe-002  37.005 -109.040 3.0
            rfpipe-003  36.995 -109.040 3.0
            rfpipe-004  36.995 -109.050 3.0
            sensor-001  37.000 -109.045 3.0
        """
        plt_name,cmp_names = self._parse_platform_components(tokens[0])

        pov_vals = tokens[1:]

        if len(pov_vals) < 3:
            raise EmoeError(f'pov field for platform {plt_name} has too few fields')

        pov_fields = [
            'latitude',
            'longitude',
            'altitude',
            'azimuth',
            'elevation',
            'speed',
            'pitch',
            'roll',
            'yaw'
        ]

        if len(pov_vals) > len(pov_fields):
            raise EmoeError(f'pov field for platform {plt_name} has too many fields')

        # set defaults
        pov_dict = {
            'latitude':0.0,
            'longitude':0.0,
            'altitude':0.0,
            'azimuth':0.0,
            'elevation':0.0,
            'speed':0.0,
            'pitch':0.0,
            'roll':0.0,
            'yaw':0.0
        }

        # and write in user specified values
        for name,value in zip(pov_fields[:len(pov_vals)], pov_vals):
            pov_dict[name] = value

        pov = POV(component_names=cmp_names,
                  latitude=float(pov_dict['latitude']),
                  longitude=float(pov_dict['longitude']),
                  altitude=float(pov_dict['altitude']),
                  azimuth=float(pov_dict['azimuth']),
                  elevation=float(pov_dict['elevation']),
                  speed=float(pov_dict['speed']),
                  pitch=float(pov_dict['pitch']),
                  roll=float(pov_dict['roll']),
                  yaw=float(pov_dict['yaw']))

        return plt_name,pov


    def _unpack_pathlosses(self, initial_conditions_dict):
        pathlosses = {}

        pathloss_lines = \
            list(filter(lambda x: len(x.strip())>0,
                        initial_conditions_dict.get('pathloss', '').split('\n')))

        for line in pathloss_lines:
            plt_name,entries = self._parse_pathloss(line.split())

            pathlosses[plt_name] = entries

        return pathlosses


    def _parse_pathloss(self, tokens):
        """
            rfpipe-001  rfpipe-002:90 rfpipe-003:120 rfpipe-004:90  sensor-001:80
            rfpipe-002                rfpipe-003:90  rfpipe-004:120 sensor-001:80
            rfpipe-003                               rfpipe-004:90  sensor-001:80
            rfpipe-004                                              sensor-001:80
        """
        plt_name,cmp_names = self._parse_platform_components(tokens[0])

        pathloss_tokens = tokens[1:]

        pathlosses = []

        for tok in pathloss_tokens:
            rmt_plt_cmp,pathloss = tok.split(':')

            rmt_plt_name,rmt_cmp_names = self._parse_platform_components(rmt_plt_cmp)

            pathlosses.append(
                Pathloss(rmt_plt_name,
                         float(pathloss),
                         cmp_names,
                         rmt_cmp_names))

        return plt_name,pathlosses


    def _unpack_antenna_pointings(self, initial_conditions_dict):
        antenna_pointings = defaultdict(lambda:[])

        antenna_pointing_lines = \
            list(filter(lambda x: len(x.strip())>0,
                        initial_conditions_dict.get('antenna_pointing', '').split('\n')))

        for line in antenna_pointing_lines:
            plt_name,pointing = self._parse_antenna_pointing(line.split())

            antenna_pointings[plt_name].append(pointing)

        return antenna_pointings


    def _parse_antenna_pointing(self, tokens):
        """
            rfpipe-001  90.0 0.0
            rfpipe-003   0.0 0.0
            rfpipe-004  45.0 0.0
        """
        plt_name,cmp_names = self._parse_platform_components(tokens[0])

        antenna_pointing_tokens = tokens[1:]

        if not len(antenna_pointing_tokens) == 2:
            raise EmoeError(f'antenna_pointing event for platform {plt_name} has the wrong number of fields')

        az,el = list(map(float,antenna_pointing_tokens))

        antenna_pointing = AntennaPointing(cmp_names, az, el)

        return plt_name,antenna_pointing


    def _parse_jam_on(self, tokens):
        plt_name,cmp_names = self._parse_platform_components(tokens[0])

        jam_on_tokens = tokens[1:]

        if not len(jam_on_tokens) == 5:
            raise EmoeError(f'jam_on event for platform {plt_name} has the wrong number of fields')

        jam_on_evt = JamOnEvent(plt_name,
                                cmp_names,
                                float(jam_on_tokens[0]), # txpower
                                int(jam_on_tokens[1]),   # bandwidth
                                int(jam_on_tokens[2]),   # period
                                int(jam_on_tokens[3]),   # duty cycle
                                [int(f) for f in jam_on_tokens[4].split(',')]) # frequencies

        return jam_on_evt


    def _parse_jam_off(self, tokens):
        plt_name,cmp_names = self._parse_platform_components(tokens[0])

        return JamOffEvent(plt_name, cmp_names)


    def _parse_end(self, tokens):
        return 'end'
