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
# See toplevel COPYING for more information.

import os
import sys

import sqlite3
import pandas as pd


def read_tables(resultdir):
    if not os.path.isdir(resultdir):
        print(f'bad directory {resultdir}, quitting.')
        exit(1)

    sqlitefiles = [f for f in os.listdir(resultdir)
                   if f.endswith('sqlite')]

    if not sqlitefiles:
        print(f'No sqlitefiles found in results directory "{resultdir}, quitting.')
        exit(2)

    sqlitefile = os.path.join(resultdir, sqlitefiles[0])

    con = sqlite3.connect(sqlitefile)

    mgen_tx = pd.read_sql('select * from mgen_tx', con)

    min_time = mgen_tx.time.min()

    mgen_rx = pd.read_sql('select * from mgen_rx', con)

    min_time = min(mgen_rx.time.min(), min_time)

    rfsignaltable = pd.read_sql('select * from rfsignaltable', con)

    min_time = min(rfsignaltable.time.min(), min_time)

    mgen_tx['relative_time'] = mgen_tx.time.apply(lambda x: x-min_time)

    mgen_rx['relative_time'] = mgen_rx.time.apply(lambda x: x-min_time)

    rfsignaltable['relative_time'] = rfsignaltable.time.apply(lambda x: x-min_time)

    return mgen_rx,mgen_tx,rfsignaltable


