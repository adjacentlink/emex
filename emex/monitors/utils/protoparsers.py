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

from collections import defaultdict,namedtuple
import logging
import pandas as pd

from otestpoint.interface.measurementtable_pb2 import MeasurementTable

from otestpoint.emex.monitor_pb2 import Measurement_emex_monitor_tables_radiomodel
from otestpoint.emex.monitor_pb2 import Measurement_emex_monitor_tables_receive
from otestpoint.emex.monitor_pb2 import Measurement_emex_monitor_tables_tdma
from otestpoint.mgen.mgen_pb2 import Measurement_mgen_flows_receive
from otestpoint.mgen.mgen_pb2 import Measurement_mgen_flows_transmit


def from_measurement(measurement):
    if measurement.type == MeasurementTable.Measurement.TYPE_SINTEGER:
        return measurement.iValue
    elif measurement.type == MeasurementTable.Measurement.TYPE_UINTEGER:
        return measurement.uValue
    elif measurement.type == MeasurementTable.Measurement.TYPE_DOUBLE:
        return measurement.dValue
    else:
        return measurement.sValue


def items_to_dfs(report_proto, probe_proto, drop_columns=[], rename_columns={}):
    dfs = []

    for item in sorted(probe_proto.DESCRIPTOR.fields_by_name.keys()):
        columns = None
        rows = []

        if item != 'description':
            messageType = type(getattr(probe_proto,item)).__name__

            if messageType == 'MeasurementTable':
                table = getattr(probe_proto,item)

                columns = ['time', 'tag'] + list(table.labels)

                int_timestamp = int(report_proto.timestamp)

                for row in table.rows:
                    rows.append(tuple([int_timestamp, report_proto.tag] + \
                                      [from_measurement(value) for value in row.values]))
                df = pd.DataFrame(rows, columns=columns)
                df.drop(columns=drop_columns, inplace=True)
                df.rename(columns=rename_columns, inplace=True)

                dfs.append((item, df))

    return dfs


def parse_rfsignal(report_proto, tag_map={}):
    """
    From:
    |NEM|AntennaId|FrequencyHz|NumSamples|AvgRxPower|AvgNoiseFloor|AvgSINR|AvgINR|

    To:
    CREATE TABLE IF NOT EXISTS "rf_signal" (
       "time" INTEGER,
       "local" TEXT,
       "remote" TEXT,
       "samples" INTEGER,
       "avg_rx_power_dBm" REAL,
       "avg_noise_floor_dBm" REAL,
       "avg_sinr_dB" REAL,
       "avg_inr_dB" REAL
    );
    """
    probe_proto = Measurement_emex_monitor_tables_receive()

    probe_proto.ParseFromString(report_proto.data.blob)

    drop_columns=['AntennaId','FrequencyHz']

    rename_columns = {
        'tag':'component',
        'NEM':'remote',
        'NumSamples':'samples',
        'AvgRxPower':'avg_rx_power_dBm',
        'AvgNoiseFloor':'avg_noise_floor_dBm',
        'AvgSINR':'avg_sinr_dB',
        'AvgINR':'avg_inr_dB'
    }

    dfs = items_to_dfs(report_proto,
                       probe_proto,
                       drop_columns=drop_columns,
                       rename_columns=rename_columns)

    for _,df in dfs:
        df.remote = df.remote.apply(lambda x: tag_map.nem_to_tag.get(x, x))

    return dfs


def parse_mgen_tx(report_proto, tag_map={}):
    """
    From:
    Src Port        Dst   Flow  Pkts  Bytes  Min Seq  Max Seq

    To:
    CREATE TABLE IF NOT EXISTS "mgen_tx" (
      "time" INTEGER,
      "source" TEXT,
      "protocol" TEXT,
      "source_port" INTEGER,
      "destination" TEXT,
      "flow" INTEGER,
      "packets" INTEGER,
      "bytes" INTEGER,
      "min_sequence" INTEGER,
      "max_sequence" INTEGER
    );
    """
    probe_proto = Measurement_mgen_flows_transmit()

    probe_proto.ParseFromString(report_proto.data.blob)

    rename_columns = {
        'tag':'source',
        'Src Port':'source_port',
        'Dst':'destination',
        'Flow':'flow',
        'Pkts':'packets',
        'Bytes':'bytes',
        'Min Seq':'min_sequence',
        'Max Seq':'max_sequence'
    }

    dfs = items_to_dfs(report_proto,
                       probe_proto,
                       rename_columns=rename_columns)

    for _,df in dfs:
        df.destination = df.destination.apply(lambda x: tag_map.ipaddress_to_tag.get(x, x))

    # add protocol
    for name,df in dfs:
        if name == 'flows_udp':
            df['protocol'] = 'udp'
        else:
            df['protocol'] = 'tcp'

    return [('mgen_tx', pd.concat([df for _,df in dfs], ignore_index=True))]


def parse_mgen_rx(report_proto, tag_map={}):
    """
    From:
    |Src|Dst|Flow|Pkts|Bytes|Dup Pkts|Dup Bytes|Avg Latency|Min Seq|Max Seq|

    To:
    CREATE TABLE IF NOT EXISTS "mgen_rx" (
      "time" INTEGER,
      "protocol" TEXT,
      "receiver" TEXT,
      "source" TEXT,
      "destination" TEXT,
      "flow" INTEGER,
      "packets" INTEGER,
      "bytes" INTEGER,
      "dup_packets" INTEGER,
      "dup_bytes" INTEGER,
      "avg_latency_seconds" REAL,
      "min_sequence" INTEGER,
      "max_sequence" INTEGER,
      "completion" REAL
    );
    """
    probe_proto = Measurement_mgen_flows_receive()

    probe_proto.ParseFromString(report_proto.data.blob)

    drop_columns=[]

    rename_columns = {
        'tag':'receiver',
        'Src':'source',
        'Dst':'destination',
        'Flow':'flow',
        'Pkts':'packets',
        'Bytes':'bytes',
        'Dup Pkts':'dup_packets',
        'Dup Bytes':'dup_bytes',
        'Avg Latency':'avg_latency',
        'Min Seq':'min_sequence',
        'Max Seq':'max_sequence'
    }

    dfs = items_to_dfs(report_proto,
                       probe_proto,
                       rename_columns=rename_columns)

    for name,df in dfs:
        df.source = df.source.apply(lambda x: tag_map.ipaddress_to_tag.get(x, x))

        df.destination = df.destination.apply(lambda x: tag_map.ipaddress_to_tag.get(x, x))

        if name == 'flows_udp':
            df['protocol'] = 'udp'
        else:
            df['protocol'] = 'tcp'

    return [('mgen_rx', pd.concat([df for _,df in dfs], ignore_index=True))]



def parse_slotstatus(report_proto, tag_map={}):
    """
    time        local Type  .25  .50  .75  1.0  >1.0
    """
    probe_proto = Measurement_emex_monitor_tables_tdma()

    probe_proto.ParseFromString(report_proto.data.blob)

    rename_columns = {
        'tag':'component',
        'Type':'type'
    }

    return items_to_dfs(report_proto,
                        probe_proto,
                        rename_columns=rename_columns)


def parse_apiqueuemetrics(report_proto, tag_map={}):
    """
    From:
    numQd  avgQDepth  numProcd   avgQWait  numTimerEvents  avgTimerLat  avgTimerLatRatio
    """
    probe_proto = Measurement_emex_monitor_tables_radiomodel()

    probe_proto.ParseFromString(report_proto.data.blob)

    rename_columns = {
        'tag':'component',
        'numQd':'num_queued',
        'avgQDepth':'avg_queue_depth',
        'numProcd':'num_processed',
        'avgQWait':'avg_queue_wait',
        'numTimerEvents':'num_timer_events',
        'avgTimerLat':'avg_timer_latency',
        'avgTimerLatRatio':'avg_timer_latency_ratio'
    }

    return items_to_dfs(report_proto,
                        probe_proto,
                        rename_columns=rename_columns)


probe_modules = ('otestpoint.mgen.flows', 'otestpoint.emex.monitor')

proto_parsers={
    'Measurement_emex_monitor_tables_receive':parse_rfsignal,
    'Measurement_emex_monitor_tables_radiomodel':parse_apiqueuemetrics,
    'Measurement_emex_monitor_tables_tdma':parse_slotstatus,
    'Measurement_mgen_flows_receive':parse_mgen_rx,
    'Measurement_mgen_flows_transmit':parse_mgen_tx
}


def aggregate(timestamp_dfs, zero_timestamp=None):
    """
    1. Aggregate all of the node's data frames into a single
       data frame for each category.

    2. Add cross table calculations - mgen completion rate
       for example.
    """
    # vertically concatenate all of the dfs that are the same name
    collected_dfs = defaultdict(lambda: [])

    for name,df in timestamp_dfs:
        collected_dfs[name].append(df)

    agg_dfs = {}
    for name,dfs in collected_dfs.items():
        df = pd.concat(dfs, ignore_index=True)

        if zero_timestamp:
            df.time = df.time.apply(lambda t: t-zero_timestamp)

        agg_dfs[name] = df

    # compute mgen_rx completions column from mgen_rx and mgen_tx
    # packet counts
    if 'mgen_rx' in agg_dfs and 'mgen_tx' in agg_dfs:
        mgen_rx = agg_dfs['mgen_rx'].set_index(['time','source','flow', 'receiver'])

        mgen_tx = agg_dfs['mgen_tx'].set_index(['time','source','flow'])

        rx_packets = mgen_rx.packets.astype(int)

        tx_packets = mgen_tx.packets.astype(int)

        # calculate completion percentage for the interval
        # replace inf (due to divide by zero) with nan
        mgen_rx['completion'] = \
            rx_packets.div(tx_packets).replace(float('inf'),float('nan'))

        agg_dfs['mgen_rx'] = mgen_rx.reset_index()

    return agg_dfs


def parse_proto(report_proto, tag_map):
    if not report_proto.data.module in probe_modules:
        return []

    """
    print()
    print(f'report '
          f'timestamp:{report_proto.timestamp} '
          f'index:{report_proto.index} '
          f'tag:{report_proto.tag}')
    print(f'report_proto.data '
          f'name:{report_proto.data.name} '
          f'modules:{report_proto.data.module} '
          f'version:{report_proto.data.version} '
          f'len:{len(report_proto.data.blob)}')
    print(f'msgs[0]: {msgs[0].decode("utf-8")}')
    """
    parser = proto_parsers.get(report_proto.data.name, None)

    if not parser:
        return []

    return parser(report_proto, tag_map)


