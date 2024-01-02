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
import re
import sys

from pandas import DataFrame

from emane_node_director.dataframewrapper import DataFrameWrapper


class EELParser:
    def parse_comment_line(self, line, nemid_to_node):
        """
        comment line, check for user embedding of nem to node information in form
        # nem:NEMID node:NODENAME
        """
        m = re.search(r'#\s*nem:\s*(?P<nemid>\d+)\s+node:\s*(?P<node>[\w\-]+)\s*', line)

        if m:
            nemid_to_node[int(m.group('nemid'))] = m.group('node')


    def parse_pov(self, eelfile):
        states = []

        column_names=['nodeid','lat','lon','alt','az','el','speed','pitch','roll','yaw','tracking']

        all_nemids_set = set([])

        nemid_to_node = {}

        rows = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0])

        last_eventtime = None

        # process eel lines
        lineno = 0
        for line in open(eelfile, 'r'):
            lineno += 1

            line = line.strip()

            # skip blank lines
            if len(line) == 0:
                continue

            if line[0] == '#':
                self.parse_comment_line(line, nemid_to_node)
                continue

            toks = line.split()

            # skip non-blank lines with too few tokens
            if len(toks)>0 and len(toks)<3:
                raise RuntimeError('Malformed EEL line %s:%d' %
                                   (eelfile, lineno))

            eventtime = float(toks[0])
            moduleid = toks[1]
            eventtype = toks[2]
            eventargs = ','.join(toks[3:])
            eventargs = eventargs.split(',')

            # ignore other events
            if not (eventtype == 'location' or eventtype == 'velocity' or eventtype == 'orientation'):
                continue

            if not eventtime == last_eventtime:
                if last_eventtime is not None:
                    state_df = DataFrame(list(rows.values()), columns=column_names)
                    state_df.set_index('nodeid', inplace=True)
                    states.append((last_eventtime, state_df))

                last_eventtime = eventtime

            # -Inf   nem:45 location gps 40.025495,-74.315441,3.0
            # <time> nem:<Id> velocity <azimuth>,<elevation>,<magnitude>
            # <time> nem:<Id> orientation <pitch>,<roll>,<yaw>
            event_nodeid = int(moduleid.split(':')[1])

            if eventtype == 'location':
                lat, lon, alt = list(map(float, eventargs[1:]))
                row = rows[event_nodeid]
                row[0] = event_nodeid
                row[1] = lat
                row[2] = lon
                row[3] = alt
                all_nemids_set.add(event_nodeid)
            elif eventtype == 'velocity':
                az, el, speed = list(map(float, eventargs))
                row[0] = event_nodeid
                row[4] = az
                row[5] = el
                row[6] = speed
                all_nemids_set.add(event_nodeid)
            elif eventtype == 'orientation':
                pitch, roll, yaw = list(map(float, eventargs))
                row[0] = event_nodeid
                row[7] = pitch
                row[8] = roll
                row[9] = yaw
                all_nemids_set.add(event_nodeid)

        state_df = DataFrame(list(rows.values()), columns=column_names)
        state_df.set_index('nodeid', inplace=True)
        states.append((last_eventtime, state_df))

        return self.format_index(states, all_nemids_set, nemid_to_node)


    def format_index(self, states, all_nemids_set, nemid_to_node):
        """
        Check to see if nem/nodes comment is embedded and if it
        covers all of the nems in the file then change the DataFrame
        index to be (nodeid,node).
        """
        nemid_to_index_map = {id:id for id in all_nemids_set}

        if nemid_to_node:
            if not all_nemids_set.issubset(nemid_to_node.keys()):
                # user supplied a mapping but didn't get them all
                # so don't add a node column
                missed_nems = ','.join(map(str, all_nemids_set.difference(nemid_to_node.keys())))
                print(f'User define nem to node mapping missing nems '
                      f'{missed_nems}, will not show nodes',
                      file=sys.stderr)
            else:
                nemid_to_index_map = {id:(id,nemid_to_node[id]) for id in all_nemids_set}

                # add node column according to mapping, nodeid is now index
                # so remove from cols and add node at front
                for _,state_df in states:
                    state_df.reset_index(inplace=True)
                    state_df['node'] = state_df.nodeid.apply(lambda x: nemid_to_node[x])
                    state_df.set_index(['nodeid','node'], inplace=True)

        output_states = []
        for tstamp,state_df in states:
            state_df.sort_index(inplace=True)
            output_states.append(
                (tstamp, DataFrameWrapper(state_df, nemid_to_index_map)))

        return output_states


    def parse_antenna_pointings(self, eelfile):
        states = []
        rows = {}

        last_eventtime = None

        all_nemids_set = set([])

        nemid_to_node = {}

        # process eel lines
        lineno = 0
        for line in open(eelfile, 'r'):
            lineno += 1

            line = line.strip()

            # skip blank lines
            if len(line) == 0:
                continue

            # skip comment lines
            if line[0] == '#':
                self.parse_comment_line(line, nemid_to_node)
                continue

            toks = line.split()

            # skip non-blank lines with too few tokens
            if len(toks)>0 and len(toks)<3:
                raise RuntimeError('Malformed EEL line %s:%d' %
                                   (eelfile, lineno))

            # -Inf nem:601 antennaprofile 3,251.29,0.031
            eventtime = float(toks[0])
            moduleid = toks[1]
            eventtype = toks[2]
            eventargs = ','.join(toks[3:])
            eventargs = eventargs.split(',')

            # ignore other events
            if not eventtype == 'antennaprofile':
                continue

            if not eventtime == last_eventtime:
                if last_eventtime is not None:
                    state_df = DataFrame(list(rows.values()),
                                         columns=['nodeid','ant_num','az','el','tracking'])
                    try:
                        # this seems necessary for python3
                        state_df = state_df.astype({'ant_num':int,'tracking':int})
                    except:
                        pass
                    state_df.set_index('nodeid', inplace=True)
                    state_df.sort_index(inplace=True)
                    states.append((last_eventtime, state_df))
                last_eventtime = eventtime

            nodeid = int(moduleid.split(':')[1])
            all_nemids_set.add(nodeid)
            ant_num = int(eventargs[0])
            az = float(eventargs[1])
            el = float(eventargs[2])

            rows[nodeid] = (nodeid,ant_num,az,el,0)

        state_df = DataFrame(list(rows.values()),
                             columns=['nodeid','ant_num','az','el','tracking'])
        try:
            # this seems necessary for python3
            state_df = state_df.astype({'ant_num':int,'tracking':int})
        except:
            pass
        state_df.set_index('nodeid', inplace=True)
        state_df.sort_index(inplace=True)
        states.append((last_eventtime,state_df))

        return self.format_index(states, all_nemids_set, nemid_to_node)
