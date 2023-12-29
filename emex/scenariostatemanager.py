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
from pandas import DataFrame

from emane_node_director.dataframewrapper import DataFrameWrapper


class ScenarioStateManager:
    def __init__(self, initial_conditions, events):
        self._pov_states,self._antenna_states = \
            self._events_to_states(initial_conditions, events)

    @property
    def pov_states(self):
        return self._pov_states

    @property
    def antenna_states(self):
        return self._antenna_states


    def _events_to_states(self, initial_conditions, events):
        pov_states,plt_name_to_id = self._pov_events_to_states(initial_conditions, events)
        antenna_states = self._antenna_events_to_states(initial_conditions, events, plt_name_to_id)
        return pov_states,antenna_states

    def _pov_events_to_states(self, initial_conditions, events):
        states = []

        column_names=[
            'nodeid','node',
            'lat','lon','alt','az','el','speed','pitch','roll','yaw','tracking'
        ]

        plt_name_to_id = {}
        plt_id_to_name = {}
        plt_id = 1

        rows = {}

        if initial_conditions:
            for ic in initial_conditions:
                if not ic.pov:
                    continue

                if not ic.platform_name in plt_name_to_id:
                    plt_name_to_id[ic.platform_name] = plt_id
                    plt_id_to_name[plt_id] = ic.platform_name
                    plt_id += 1

                rows[ic.platform_name] = (
                    plt_name_to_id[ic.platform_name],
                    ic.platform_name,
                    ic.pov.latitude,
                    ic.pov.longitude,
                    ic.pov.altitude,
                    ic.pov.speed,
                    ic.pov.azimuth,
                    ic.pov.elevation,
                    ic.pov.pitch,
                    ic.pov.roll,
                    ic.pov.yaw,
                    0
                )

            state_df = DataFrame(rows.values(), columns=column_names)
            state_df.set_index(['nodeid','node'], inplace=True)
            states.append((float('-inf'), state_df))

        for eventtime,eventdict in sorted(events.items()):
            for eventtype,eventlist in eventdict.items():
                if not eventtype == 'pov':
                    continue

                # build data frame
                for plt_name,event in eventlist:
                    if not plt_name in plt_name_to_id:
                        plt_name_to_id[plt_name] = plt_id
                        plt_id_to_name[plt_id] = plt_name
                        plt_id += 1

                    rows[plt_name] = (
                        plt_name_to_id[plt_name],
                        plt_name,
                        event.latitude,
                        event.longitude,
                        event.altitude,
                        event.speed,
                        event.azimuth,
                        event.elevation,
                        event.pitch,
                        event.roll,
                        event.yaw,
                        0
                    )

            state_df = DataFrame(rows.values(), columns=column_names)
            state_df.set_index(['nodeid','node'], inplace=True)
            states.append((eventtime, state_df))

        id_to_index = {id:(id,name) for id,name in plt_id_to_name.items()}
        wrapped_states = [(evttime, DataFrameWrapper(state_df, id_to_index))
                          for evttime,state_df in states]

        return wrapped_states,plt_name_to_id


    def _antenna_events_to_states(self, initial_conditions, events, plt_name_to_id):
        states = []

        column_names=['nodeid','node',
                      'ant_num','az','el','tracking']

        plt_id_to_name = {id:name for name,id in plt_name_to_id.items()}
        plt_id = max(plt_id_to_name) if plt_id_to_name else 1

        rows = {}

        if initial_conditions:
            for ic in initial_conditions:
                if not ic.antenna_pointings:
                    continue

                if not ic.platform_name in plt_name_to_id:
                    plt_name_to_id[ic.platform_name] = plt_id
                    plt_id_to_name[plt_id] = ic.platform_name
                    plt_id += 1

                for pointing in ic.antenna_pointings:
                    rows[ic.platform_name] = (
                        plt_name_to_id[ic.platform_name],
                        ic.platform_name,
                        1,
                        pointing.azimuth,
                        pointing.elevation,
                        0
                    )

            state_df = DataFrame(rows.values(), columns=column_names)
            state_df.set_index(['nodeid','node'], inplace=True)
            states.append((float('-inf'), state_df))

        for eventtime,eventdict in sorted(events.items()):
            for eventtype,eventlist in eventdict.items():
                if not eventtype == 'antenna_pointing':
                    continue

                # build data frame
                for plt_name,event in eventlist:
                    if not plt_name in plt_name_to_id:
                        plt_name_to_id[plt_name] = plt_id
                        plt_id_to_name[plt_id] = plt_name
                        plt_id += 1

                    rows[plt_name] = (
                        plt_name_to_id[plt_name],
                        plt_name,
                        1,
                        event.azimuth,
                        event.elevation,
                        0
                    )

            state_df = DataFrame(rows.values(), columns=column_names)
            state_df.set_index(['nodeid','node'], inplace=True)
            states.append((eventtime, state_df))

        id_to_index = {id:(id,name) for id,name in plt_id_to_name.items()}
        wrapped_states = [(evttime, DataFrameWrapper(state_df, id_to_index))
                          for evttime,state_df in states]

        return wrapped_states
