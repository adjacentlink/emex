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

import logging
import os
import shutil

from pandas import DataFrame

from emex.trafficmanager import TrafficManager
from emex.emaneeventmanager import EmaneEventManager
from emex.jammingmanager import JammingManager
from emex.emoemessages import StartSimpleFlowRequest,StopFlowRequest


class ScenarioManager:
    NEMID_MAP_FILE='/tmp/etce/config/doc/nemid_map.csv'
    EMEXD_CONFIG_FILE='/tmp/etce/config/doc/emexd-config.csv'

    def __init__(self, broker):
        self._broker = broker

        self._sequence = 1

        nemid_map,antenna_profileid_map = self._read_nemid_profileid_map_file()

        self._emexd_config_map = self._read_emexd_config_file()

        self._tm = TrafficManager()

        self._eem = EmaneEventManager(nemid_map, antenna_profileid_map)

        self._jm = JammingManager(nemid_map, antenna_profileid_map)


    def connect(self):
        self._tm.connect()

        return self._tm.connected


    def handle_requests(self, remote, client_sequence, requests):
        logging.debug(f'scenario_manager handle_requests')

        start_ok,start_message = self._tm.start_flows(requests['flow_on'])

        stop_ok,stop_message = self._tm.stop_flows(requests['flow_off'])

        events_ok,events_message = self._eem.send_events(requests['emane_events'])

        jamming_ok,jamming_message = self._jm.send_events(requests['jamming_events'])

        message = f'ok for client_sequence={client_sequence}'

        ok = start_ok and stop_ok and events_ok and jamming_ok

        if not ok:
            if not start_ok:
                message = start_message
            elif not stop_ok: # not stop_ok
                message = stop_message
            elif not events_ok:
                message = events_message
            else:
                message = jamming_message

        flows_df = self._tm.get_flows() \
            if requests['list_flows_flag'] else DataFrame()

        self._broker.send_result(remote,
                                 client_sequence,
                                 ok,
                                 message,
                                 flows_df)


    def clean_up(self, did_run):
        # remove emoe created subdirectories in the emex directory when
        # configured to do so
        if self._emexd_config_map['emexdirectory-action'] == 'keep':
            return

        if self._emexd_config_map['emexdirectory-action'] == 'delete' or did_run:
            """
            delete files and subdirectories in /tmp/etce created within
            the container (owned by root or with subdirectories written by root)
            when configure to do so:

                1. when emexdirectory-action is "delete"
                2. when emexdirectory-action is "deleteonsuccess" and the emoe reached the
                   RUNNINGstate

            drwxr-xr-x 7 user       user         200 Aug 18 09:44 config
            drwxr-xr-x 6 root       root         200 Aug 18 09:44 current_test
            drwxr-xr-x 3 user       user          60 Aug 18 09:44 data
            -rw-rw-rw- 1 root       root       37515 Aug 18 09:45 emexcontainerd.log
            ---------- 1 root       root       17110 Aug 18 09:44 etce.log
            drwxr-xr-x 2 root       root         280 Aug 18 09:44 lock
            drwxr-xr-x 5 user       user         120 Aug 18 09:44 lxcroot
            """
            logging.info(f'cleanup /tmp/etce/current_test')
            shutil.rmtree('/tmp/etce/current_test', ignore_errors=True)

            logging.info(f'cleanup /tmp/etce/data')
            shutil.rmtree('/tmp/etce/data', ignore_errors=True)

            logging.info(f'cleanup /tmp/etce/lxcroot')
            shutil.rmtree('/tmp/etce/lxcroot', ignore_errors=True)

            logging.info(f'cleanup /tmp/etce/lock')
            shutil.rmtree('/tmp/etce/lock', ignore_errors=True)

            if os.path.isfile('/tmp/etce/etce.log'):
                logging.info(f'cleanup /tmp/etce/etce.log')
                os.remove('/tmp/etce/etce.log')

            if os.path.isfile('/tmp/etce/emexcontainerd.log'):
                logging.info(f'cleanup /tmp/etce/emexcontainerd.log')
                os.remove('/tmp/etce/emexcontainerd.log')


    def _read_nemid_profileid_map_file(self):
        nemid_map = {}
        antenna_profileid_map = {}

        for line in open(ScenarioManager.NEMID_MAP_FILE):
            line = line.strip()

            if not line:
                continue

            plt_name,c_name,nemid,profileid = line.split(',')

            logging.info(
                f'map plt:{plt_name} '
                f'cmp:{c_name} '
                f'nemid:{nemid} '
                f'profileid:{profileid}')

            nemid_map[(plt_name,c_name)] = int(nemid)

            if profileid.strip():
                antenna_profileid_map[(plt_name,c_name)] = int(profileid)

        return nemid_map,antenna_profileid_map


    def _read_emexd_config_file(self):
        emexd_config_map = {}

        for line in open(ScenarioManager.EMEXD_CONFIG_FILE):
            line = line.strip()

            if not line:
                continue

            name,val = line.split(',')

            logging.info(
                f'name:{val}')

            emexd_config_map[name] = val

        return emexd_config_map
