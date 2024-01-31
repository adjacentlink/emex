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

import logging
import sqlite3
import traceback


class SqliteWriter:
    def __init__(self, outputfile, verbose):
        self._outputfile = outputfile

        self._verbose = verbose

        self._connection = None


    def _open(self):
        if self._connection:
            return

        try:
            logging.info(f'creating sqlite connection to {self._outputfile}')
            self._connection = sqlite3.connect(self._outputfile)
        except Exception as e:
            logging.error(e)
            exit(1)

        self._connection.execute("PRAGMA synchronous = 0;");
        self._connection.execute("DROP TABLE IF EXISTS apiqueuemetrics;")
        self._connection.execute("DROP TABLE IF EXISTS mgen_rx;")
        self._connection.execute("DROP TABLE IF EXISTS mgen_tx;")
        self._connection.execute("DROP TABLE IF EXISTS rfsignaltable;")
        self._connection.execute("DROP TABLE IF EXISTS slottiminghistogram;")

        self._connection.commit()


    def process_dataframes(self, timestamp, dfs):
        self._open()

        try:
            for name,df in dfs.items():
                if not df.empty:
                    logging.debug(f'simple_print_callable writing to db: {name}')

                    df.to_sql(name,
                              con=self._connection,
                              if_exists='append',
                              index=False)
                else:
                    logging.debug(f'simple_print_callable not writing empty df to db: {name}')

            if self._verbose:
                for name,df in dfs.items():
                    logging.info(name)
                    logging.info(df)

        except:
            logging.error(traceback.format_exc())


    def close(self):
        self._connection.close()
