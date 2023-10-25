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


from collections import defaultdict
import cmd
import sys

from emex.emexdrpcclient import EmexdRpcClient
from emex.antenna import Antenna
from emex.platform import Platform
from emex.emaneeventmessages import POV,AntennaPointing
from emex.initialcondition import InitialCondition
from emex.emoe import Emoe


class Shell(cmd.Cmd):
    prompt = '(emex): '

    def __init__(self, args):
        super().__init__()

        self._address = args.address

        self._rpcclient = EmexdRpcClient(endpoint=(args.address, args.port))

        self.antennatypes = {}

        self.antennas = {}

        self.platformtypes = {}

        self.platforms = {}

        self.antenna_pointings = {}

        self.initial_conditions = {}

        self.do_listmodels()


    def do_listmodels(self, arg=None):
        """
        usage: listmodels

        description: fetches and lists available platform and antenna
             types.
        """
        self.antennatypes, self.platformtypes = self._rpcclient.getmodels()

        print('#### PlatformTypes')
        for pt_name in sorted(self.platformtypes):
            print(f'   {pt_name}')
        print()

        print('#### AntennasTypes')
        for at_name in sorted(self.antennatypes):
            print(f'   {at_name}')
        print()


    def do_listplatformtypes(self, arg=None):
        """
        usage: listplatforms [PLATFORMNAME]

        description: List installed platform information. The command
             defaults to displaying information for all available
             platforms. Specifying PLATFORMNAME limits output to
             that platform only.
        """
        display_all = True
        model_name = None
        if arg:
            display_all = False
            model_name = arg.split()[0]

        for pt_name, pt in sorted(self.platformtypes.items()):
            if display_all or (pt.name == model_name):
                print('###############')
                print(pt)
        print()


    def do_listantennatypes(self, arg=None):
        """
        usage: listantennatypes [ANTENNANAME]

        description: List available antenna types. The command
             defaults to displaying information for all available
             antenna typess. Specifying ANTENNANAME limits output to
             that antenna type only.
        """
        display_all = True
        model_name = None
        if arg:
            display_all = False
            model_name = arg.split()[0]

        for at_name, at in sorted(self.antennatypes.items()):
            if display_all or (at.name == model_name):
                print('###############')
                print(at)
        print()


    def do_listantennas(self, arg=None):
        """
        usage: listantennas [ANTENNANAME]

        description: List built antennas. The command
             defaults to displaying information for all available
             antennas. Specifying ANTENNANAME limits output to
             that antenna only.
        """
        display_all = True
        antenna_name = None
        if arg:
            display_all = False
            antenna_name = arg.split()[0]

        for _,antenna in sorted(self.antennas.items()):
            if display_all or (antenna.name == antenna_name):
                print('###############')
                print(antenna)
        print()


    def do_setparam(self, arg):
        """
        usage: setparam PLATFORMNAME [component.group.param=value[,value]+]*

        description: Set one or more parameter values for a selected platform.
        """
        tokens = arg.split()

        if len(tokens) < 2:
            print(self.do_setparam.__doc__)
            return

        platformname = tokens[0]

        platform = self.platforms.get(platformname, None)

        if not platform:
            print(f'"{platformname}" not found in built platforms. Ignoring.',
                  file=sys.stderr)
            return

        try:
            params = self._parse_params(tokens[1:])
        except ValueError as ve:
            print(ve)
            return

        try:
            for c_name, pg_name, p_name, value_list in params:
                if pg_name == 'phy' and p_name == 'antenna0':
                    self.set_antenna_parameter(platform, c_name, pg_name, p_name, value_list)
                else:
                    platform.set_param(c_name, pg_name, p_name, value_list)
        except ValueError as ve:
            print(ve)


    def do_addlabel(self, arg):
        """
        usage: addlabel PLATFORMNAME.COMPONENTNAME label

        description: Add a label to a platform component.
        """
        tokens = arg.split()

        if not len(tokens) == 2:
            print(self.do_addlabel.__doc__)
            return

        platform_component_toks = tokens[0].split('.')

        if not len(platform_component_toks) == 2:
            print(self.do_addlabel.__doc__)
            return

        platformname, componentname = platform_component_toks

        label = tokens[1]

        platform = self.platforms.get(platformname, None)

        if not platform:
            print(f'Platform "{platformname}" already exists. Ignoring.',
                  file=sys.stderr)
            return

        try:
            platform.add_label(componentname, label)
        except ValueError as ve:
            print(ve)


    def do_buildplatform(self, arg):
        """
        usage: buildplatform PLATFORMNAME PLATFORMTYPE [component.group.param=value[,value]+]*

        description: Build a platform named PLATFORMNAME of PLATFORMTYPE with
        the specified configuration.
        """
        tokens = arg.split()

        if len(tokens) < 2:
            print(self.do_buildplatform.__doc__)
            return

        platformname = tokens[0]

        platformtype = tokens[1]

        component_params = tokens[2:]

        if not platformtype in self.platformtypes:
            print(f'"{platformtype}" not found in available platform types. Ignoring.',
                  file=sys.stderr)
            return

        if platformname in self.platforms:
            print(f'Platform "{platformname}" already exists. Ignoring.',
                  file=sys.stderr)
            return

        user_config = defaultdict(lambda: {})

        for paramtoks in component_params:
            name_val_toks = paramtoks.split('=')

            if not len(name_val_toks) == 2:
                print(f'malformed parameter "{paramtoks}".')
                return

            group_name, value_str = name_val_toks

            component_group_name_toks = group_name.split('.')

            if not len(component_group_name_toks) == 3:
                print(f'paramter format should be "component.group.name"')
                return

            component, group, param = component_group_name_toks

            values = value_str.split(',')

            if param == 'antenna0' and not values[0] in self.antennas:
                print(f'unknown antenna name "{values[0]}"')
                return

            if not group in user_config[component]:
                user_config[component][group] = {param: values}
            else:
                user_config[component][group].extend({param: values})

        self.platforms[platformname] = \
            Platform(platformname,
                     self.platformtypes[platformtype],
                     user_config)


    def do_listplatforms(self, arg):
        """
        usage: listplatforms [PLATFORMNAME]*

        description: List all current platforms
        """
        names = arg.split() if arg else self.platforms.keys()

        for name in names:
            platform = self.platforms.get(name, None)

            if platform:
                print('########')
                print(platform)
            else:
                print(f'Unknown platform "{name}".')


    def do_listinitialconditions(self, arg):
        """
        usage: listinitialconditions [PLATFORMNAME]*

        description: List current set of initial conditions, or just
             those for the specified platform name(2).
        """
        names = arg.split() if arg else self.initial_conditions.keys()

        for name in names:
            initial_condition = self.initial_conditions.get(name, None)

            if initial_condition:
                print('########')
                print(initial_condition)
            else:
                print(f'Unknown platform "{name}".')


    def do_buildantenna(self, arg):
        """
        usage: buildantenna ANTENNANAME ANTENNATYPE [param=value[,value]+]*

        description: Build an antenna named ANTENNANAME of ANTENNATYPE with
        the specified configuration. The ANTENNANAME of any built antenna
        can be referenced when building a platform to assign the antenna
        to the platform for use - usually as one of the radio component
        phy.antenna0 parameters.
        """
        tokens = arg.split()

        if len(tokens) < 2:
            print(self.do_buildantenna.__doc__)
            return

        antennaname = tokens[0]

        antennatype = tokens[1]

        component_params = tokens[2:]

        if not antennatype in self.antennatypes:
            print(f'"{antennatype}" not found in available antenna types. Ignoring.',
                  file=sys.stderr)
            return

        if antennaname in self.antennas:
            print(f'Antenna "{antennaname}" already exists. Ignoring.',
                  file=sys.stderr)
            return

        user_config = defaultdict(lambda: [])

        for paramtoks in component_params:
            name_val_toks = paramtoks.split('=')

            if not len(name_val_toks) == 2:
                print(f'malformed parameter "{paramtoks}".')
                return


            param_name, value_str = name_val_toks

            values = value_str.split(',')

            user_config[param_name] = values

        self.antennas[antennaname] = \
            Antenna(antennaname,
                    self.antennatypes[antennatype],
                    user_config)


    def do_clear(self, arg):
        """
        usage: clear

        description: Clear current built state (platforms and
             initial conditions)
        """
        self.platforms.clear()

        self.antenna_pointings.clear()

        self.antennas.clear()

        self.initial_conditions.clear()


    def set_antenna_parameter(self, platform, c_name, pg_name, p_name, value_list):
        """
        set the component antenna* parameter and update the associated initial
        condition accordingly.
        """
        if not platform.has_component(c_name):
            print(f'Platform "{platform.name}". Does not have a component '
                  f'{c_name}. Ignoring.',
                  file=sys.stderr)
            return

        antennaname = value_list.pop(0)

        # omni_gain is a builtin recognized type, just set it
        if antennaname.startswith('omni'):
            platform.set_param(c_name, pg_name, p_name, antennaname)
            return

        # check that antennaname is the name of a built antenna
        if not antennaname in self.antennas:
            print(f'"{antennaname}" does not name a built antenna. Ignoring.',
                  file=sys.stderr)
            return

        platform.set_param(c_name, pg_name, p_name, antennaname)


    def do_setlocation(self, arg):
        """
        usage: setlocation PLATFORMNAME[.COMPONENTNAME] LAT LON ALT [SPEED [AZ [EL [PITCH [ROLL [YAW]]]]]]

        description: add an initial position, orientation and velocity
             for the given platform. Initial POV is optional.
        """
        tokens = arg.split()

        if len(tokens) < 4 or len(tokens) > 9:
            print(self.do_setlocation.__doc__)

            return

        plt_cmp = tokens[0]

        plt_cmp_tokens = plt_cmp.split('.')

        platformname = plt_cmp_tokens[0]

        componentname = plt_cmp_tokens if len(plt_cmp_tokens)>1 else []

        args = list(map(float, tokens[1:]))

        if not platformname in self.platforms:
            print(f'Unknown platform "{platformname}". Ignoring.',
                  file=sys.stderr)

            return

        if componentname and not self.platforms[platformname].component_by_name(componentname):
            print(f'Unknown component "{componentname}". Ignoring.',
                  file=sys.stderr)

            return

        platform_initial_condition = self.initial_conditions.get(platformname, None)

        args = [componentname] + args

        pov = POV(*args)

        if platform_initial_condition:
            platform_initial_condition.pov = pov
        else:
            self.initial_conditions[platformname] = InitialCondition(platformname, pov=pov)


    def do_checkemoe(self, arg):
        """
        usage: checkemoe EMOENAME

        description: creates a emoe named EMOENAME consisting
             of all current platforms and sends a schenario
             check request to the emexd servers to check
             if the emoe is correct and can be allocated
             with currently available resources.
        """
        tokens = arg.split()

        if not len(tokens) == 1:
            print(self.do_checkemoe.__doc__)
            return

        emoe_name = tokens[0]

        emoe = None

        try:
            emoe = Emoe(emoe_name,
                        self.platforms.values(),
                        self.initial_conditions.values())

        except ValueError as ve:
            print(ve)

            return

        print('Client: Sending CheckEmoeRequest')

        reply = self._rpcclient.checkemoe(emoe)

        if not reply.result:
            print(f'Emoe "{reply.emoe_name}" fails with ' \
                  f'message "{reply.message}".')
            return

        print(f'Emoe {reply.emoe_name}: {reply.message}')


    def do_startemoe(self, arg):
        """
        usage: startemoe EMOENAME

        description: creates a emoe named EMOENAME consisting
             of all current platforms and sends a schenario
             start request to the emexd servers to start
             if the emoe is correct and can be allocated
             with currently available resources.
        """
        tokens = arg.split()

        if not len(tokens) == 1:
            print(self.do_startemoe.__doc__)
            return

        emoe_name = tokens[0]

        emoe = None

        # set antenna_pointings
        for platformname,antenna_pointing in self.antenna_pointings.items():
            platform_initial_condition = self.initial_conditions.get(platformname, None)

            if platform_initial_condition:
                platform_initial_condition.add_antenna_pointing(antenna_pointing)
            else:
                self.initial_conditions[platformname] = \
                    InitialCondition(platformname,
                                     antenna_pointings=[antenna_pointing])

        try:
            emoe = Emoe(emoe_name,
                        self.platforms.values(),
                        self.initial_conditions.values())
        except ValueError as ve:
            print(ve)

            return

        print('Client: Sending StartEmoeRequest')
        reply = self._rpcclient.startemoe(emoe)

        if not reply.result:
            print(f'Emoe "{reply.emoe_name}" fails with ' \
                  f'message "{reply.message}".')
            return

        print(f'Emoe {reply.emoe_name}: {reply.message}')

        # clear the built platform and initial conditions once
        # they've been incorporated into an emoe
        self.do_clear(None)


    def do_listemoes(self, arg):
        """
        usage: listemoes

        description: list existing emoes with their current state.
        """
        print('Client: Sending ListEmoesRequest')
        reply = self._rpcclient.listemoes()

        print('###############')
        print(f'emexd server: {self._address}')
        print(f'total cpus: {reply.total_cpus}')
        print(f'available cpus: {reply.available_cpus}')
        print('Emoes:')
        for entry in reply.emoe_entries:
            print('###############')

            print(f'handle: {entry.handle}')

            print(f'name: {entry.emoe_name}')

            print(f'state: {entry.state.name}')

            print(f'cpus: {entry.cpus}')

            print(f'accesors:')
            for accessor in entry.service_accessors:
                print(f'   {accessor.name}: {accessor.ip_address}:{accessor.port}')

            print()


    def do_stopemoe(self, arg):
        """
        usage: stopemoe EMOEHANDLE

        description: stop the emoe identified by EMOEHANDLE and start analysis.
        """
        tokens = arg.split()

        if not len(tokens) == 1:
            print(self.do_stopemoe.__doc__)
            return

        emoe_handle = tokens[0]

        emoe = None

        print('Client: Sending StopEmoeRequest')
        reply = self._rpcclient.stopemoe(emoe_handle)

        if not reply.result:
            print(f'Emoe "{reply.emoe_name}" fails with ' \
                  f'message "{reply.message}".')
            return

        print(f'Emoe {reply.emoe_name}: {reply.message}')


    def do_exit(self, arg):
        """
        exit: Exit and close
        """
        self._rpcclient.close()

        return True


    def _parse_params(self, param_args):
        param_name_vals = []

        for param_arg in param_args:
            name_val_toks = param_arg.split('=')

            if not len(name_val_toks) == 2:
                raise ValueError(f'malformed parameter "{name_val_toks}".')

            group_name, value_str = name_val_toks

            component_group_name_toks = group_name.split('.')

            if not len(component_group_name_toks) == 3:
                raise ValueError(f'paramter format should be "component.group.name"')

            component, group, param = component_group_name_toks

            values = value_str.split(',')

            param_name_vals.append((component, group, param, values))

        return param_name_vals
