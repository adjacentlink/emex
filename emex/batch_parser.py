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
import signal
import sys


def run(args):
    # import in function scope to prevent logging calls
    # before the root script can configure logging
    import logging
    from emex.batchrunner import BatchRunner

    for scenariofile in args.scenariofiles:
        if not os.path.isfile(scenariofile):
            print(f'Cannot find scenario file "{scenariofile}". Quitting.',
                  file=sys.stderr)
            exit(1)

    if args.monitor and not args.output_path:
        print(f'Found "monitor" argument without "output-path" argument. Quitting.')
        exit(2)

    if args.output_path:
        if not os.path.exists(args.output_path):
            print(f'Creating output-path "{args.output_path}.')
            os.makedirs(args.output_path)

        elif not os.path.isdir(args.output_path):
            print(f'Found output-path "{args.output_path}" is not a directory. Quitting.')
            exit(3)

        else:
            print(f'Will write outputs to existing output-path "{args.output_path}"')

    runner = BatchRunner(args)

    signal.signal(signal.SIGINT, runner.do_stop)
    signal.signal(signal.SIGQUIT, runner.do_stop)
    runner.run()


def add_batch_parser(subparsers):
    """
    Configure emex run command
    """

    batch_parser = \
        subparsers.add_parser('batch',
                              help='Run one or more scenarios in batch.')

    batch_parser.set_defaults(func=run)

    batch_parser.add_argument('--address',
                              default='127.0.0.1',
                              help='IPV4 address of the emexd server. Default: 127.0.0.1.')
    batch_parser.add_argument('--port',
                              type=int,
                              default=49901,
                              help='Listening port of the emexd server. Default: 49901.')
    batch_parser.add_argument('--output-path',
                              metavar='OUTPUTPATH',
                              default=None,
                              help='Directory for output data artifacts. For '
                              'each scenario that is run, a subdirectory is '
                              'created in the output directory in format '
                              '"emoe_handle.emoe_name". Default: .')
    batch_parser.add_argument('--numtrials',
                              metavar='NUMTRIALS',
                              default=1,
                              type=int,
                              help='The number of times to run each scenario.')
    batch_parser.add_argument('--monitor',
                              action='store_true',
                              help='Run the emex monitor for each emoe.')
    batch_parser.add_argument('scenariofiles',
                              nargs='+',
                              metavar='SCENARIOFILES',
                              help='One or more EMEX scenario files to run in batch.')
