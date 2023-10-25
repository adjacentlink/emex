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
import os
import shlex
import signal
import subprocess

from lxml import etree
import pandas as pd
import sqlite3


class Emex:
    """
    The EMEX monitor execs emex-monitor script to collect MGEN
    and RF Signal table data from the EMOE opentestpoint broker
    publish stream and writes it to sqlite database at the output
    directory specified.
    """
    def __init__(self, emoe):
        self._emoe = emoe


    def _write_map_file(self, map_file):
        """
        <emex-monitor-tag-map>
          <nem>
            <map tag='lteenb-001' nem='581'/>
            <map tag='lteue-001' nem='501'/>
            <map tag='lteue-002' nem='502'/>
            <map tag='lteue-003' nem='503'/>
          </nem>
          <ip-address>
            <map tag='lteepc-001' ip-address='10.0.5.100'/>
            <map tag='lteue-001' ip-address='10.0.5.1'/>
            <map tag='lteue-002' ip-address='10.0.5.2'/>
            <map tag='lteue-003' ip-address='10.0.5.3'/>
          </ip-address>
        </emex-monitor-tag-map>
        """
        root_elem = etree.Element('emex-monitor-tag-map')

        nem_elem = etree.SubElement(root_elem, 'nem')

        ip_address_elem = etree.SubElement(root_elem, 'ip-address')

        for platform in self._emoe.platforms:
            for c_name,pg_name,p_name,value in platform.get_params():
                hostname = f'{platform.name}-{c_name}'

                pg_p_name = f'{pg_name}.{p_name}'

                if pg_p_name == 'emane.nemid':
                    map_elem = etree.SubElement(nem_elem, 'map')

                    map_elem.set('tag', hostname)

                    map_elem.set('nem', str(value[0]))

                elif pg_p_name == 'net.ipv4address':
                    map_elem = etree.SubElement(ip_address_elem, 'map')

                    map_elem.set('tag', hostname)

                    map_elem.set('ip-address', value[0])

        # write file
        root_tree = root_elem.getroottree()

        root_tree.write(map_file, pretty_print=True)


    def run(self, output_path, otestpoint_publish_endpoint):
        """
        emex-monitor [-h]
                  [--tag-map TAG_MAP]
                  [--verbose]
                  [--pid-file PID_FILE]
                  [--daemonize]
                  [--log-file FILE]
                  [--log-level LEVEL]
                  endpoint
                  output-file
        """

        self._output_path = output_path

        self._map_file = os.path.join(output_path, 'emex-tag-map.xml')

        self._write_map_file(self._map_file)

        ipaddress,port = otestpoint_publish_endpoint

        str_endpoint = f'{ipaddress}:{port}'

        log_file = os.path.join(self._output_path, 'emex-monitor.log')

        sqlite_file = os.path.join(self._output_path, 'emex-monitor.sqlite')

        cmd = 'emex-monitor'

        args = f'--tag-map {self._map_file} ' \
            f'--log-file {log_file} ' \
            f'--log-level info ' \
            f'{str_endpoint} ' \
            f'{sqlite_file}'

        cmdline = f'{cmd} {args}'

        logging.debug(f'run emex-monitor: "{cmdline}"')

        self._process = subprocess.Popen(shlex.split(cmdline),
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.STDOUT,
                                         shell=False)

        self._sqlite_file = sqlite_file


    def stop(self, flows_df=None):
        logging.debug(f'kill emex-monitor pid={self._process.pid}')

        self._process.send_signal(signal.SIGINT)

        self._process.wait()

        con = sqlite3.connect(self._sqlite_file)

        con.execute("DROP TABLE IF EXISTS mgen_flows;")

        schema = 'CREATE TABLE "mgen_flows" (' \
            '"flow_name" TEXT, '         \
            '"flow_id" INT, '            \
            '"source" TEXT, '            \
            '"destination" TEXT, '       \
            '"tos" INT, '                \
            '"ttl" INT, '                \
            '"proto" INT, '              \
            '"flow_pattern" INT, '       \
            '"size_bytes" INT , '        \
            '"packet_rate" DOUBLE, '     \
            '"jitter_fraction" DOUBLE, ' \
            'PRIMARY KEY ("flow_id", "source", "destination"));'

        con.execute(schema)

        if isinstance(flows_df, pd.DataFrame):
            flows_df.drop(columns=['active', 'ttl']).to_sql('mgen_flows',
                                                            con,
                                                            if_exists='append',
                                                            index=False)
        else:
            logging.debug(f'Received flows_df type {type(flows_df)}, '
                          f'expected DataFRame. Ignoring')

        con.commit()

        con.close()

