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


def run(args):
    # import in function scope to prevent logging calls
    # before the root script can configure logging
    import logging
    from emex.scenariorunner import ScenarioRunner
    from emex.yamlscenariobuilder import YamlScenarioBuilder

    try:
        if not os.path.isfile(args.scenariofile):
            print(f'Cannot find scenario file "{args.scenariofile}", quitting',
                  file=sys.stderr)
            exit(1)

        if args.output_path:
            if os.path.exists(args.output_path):
                print(f'output-path "{args.output_path}" already exists. Quitting')
                exit(2)

        runner = ScenarioRunner((args.address, args.port),
                                args.emoename,
                                YamlScenarioBuilder(args.scenariofile),
                                args.output_path,
                                args.monitor)

        logging.info(f'{args.emoename} requires {runner.required_cpus()} cpus '
                     f'from server that has {runner.available_cpus()} available '
                     f'from {runner.total_cpus()} total allocated to it')

        ok,message = runner.check()

        if not ok:
            logging.warning(f'{args.emoename} failed check with message "{message}"')
            exit(3)

        runner.run()
    except KeyboardInterrupt:
        pass


def add_run_parser(subparsers):
    """
    Configure emex run command
    """

    run_parser = \
        subparsers.add_parser('run',
                              help='Run an EMEX scenario from an EMEX yaml file.')

    run_parser.set_defaults(func=run)

    run_parser.add_argument('--address',
                            default='127.0.0.1',
                            help='IPV4 address of the emexd server. Default: 127.0.0.1.')
    run_parser.add_argument('--port',
                            type=int,
                            default=49901,
                            help='Listening port of the emexd server. Default: 49901.')
    run_parser.add_argument('--output-path',
                            metavar='OUTPUTPATH',
                            default=None,
                            help='Directory for output data artifacts. By '
                            'default, a sub-directory will be created in '
                            'the current directory emoe_handle.emoe_name.')
    run_parser.add_argument('--monitor',
                            action='store_true',
                            help='Run the emex monitor and save output to output-path.')
    run_parser.add_argument('emoename',
                            metavar='EMOENAME',
                            help='Name for the EMOE.')
    run_parser.add_argument('scenariofile',
                            metavar='SCENARIOFILE',
                            help='The EMEX scenario file.')
