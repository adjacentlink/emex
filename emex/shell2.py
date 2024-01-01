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

import cmd

from emane_node_director.antennapointer import AntennaPointer
from emane_node_director.nodetracker import NodeTracker
from emane_node_director.pathlosscalculator import PathlossCalculator
from emex.emoemessages import (
    TrafficProtocolType,
    SimpleTrafficFlowType,
    StartSimpleFlowRequest,
    StopFlowRequest,
    JamOnEvent,
    JamOffEvent
)


class Shell2(cmd.Cmd):
    intro = 'EMANE Node Director. Type help or ? to list commands.\n'
    prompt = 'director> '

    def __init__(self, pov_states, antenna_pointing_states, publisher, writer, args):
        cmd.Cmd.__init__(self)

        self._publisher = publisher

        self._writer = writer

        self._tracker = NodeTracker(pov_states)

        self._pointer = AntennaPointer(antenna_pointing_states, self._tracker)

        self._pathloss_calc = PathlossCalculator(args, self._tracker, self._pointer)

        self._traffic_flows = {}

        self._altstep = args.altstep

        self._latlonstep = args.latlonstep

        self._anglestep = args.anglestep

        self._writetime = 0.0

        self._timestep = args.timestep

        self._statefile = args.statefile

        self._statefd = None

        self._quiet = args.quiet

        self._direction_handler = {
            'n':self.move_north,
            's':self.move_south,
            'e':self.move_east,
            'w':self.move_west,
            'u':self.move_up,
            'd':self.move_down
        }

        self._azimuth_handler = {
            'cw':self.azimuth_clockwise,
            'cc':self.azimuth_counter_clockwise
        }

        self._elevation_handler = {
            'u':self.elevation_up,
            'd':self.elevation_down
        }

        self._pitch_handler = {
            'u':self.pitch_up,
            'd':self.pitch_down,
        }

        self._roll_handler = {
            'cw':self.roll_clockwise,
            'cc':self.roll_counter_clockwise,
        }

        self._yaw_handler = {
            'cw':self.yaw_clockwise,
            'cc':self.yaw_counter_clockwise,
        }

        self._pointing_handler = {
            'u':self.point_up,
            'd':self.point_down,
            'cw':self.point_clockwise,
            'cc':self.point_counter_clockwise,
        }

        # send initial positions
        self._send()


    def _send(self):
        self._publisher.publish_locations(self._tracker.current)

        self._publisher.publish_antenna_profiles(self._pointer.current)

        self._publisher.publish_pathlosses(self._pathloss_calc.current)

        if not self._quiet:
            self.do_show()


    def do_exit(self, arg):
        """
        Close and exit.

        exit
        """
        return True


    def do_reset(self, arg):
        """
        Reset all Nodes to their initial state.

        reset
        """
        # TODO, handle resetting just individual node args
        self._tracker.reset()

        self._pointer.reset()

        self._send()


    def do_show(self, arg=None):
        """
        Show the current state of one or more Nodes.

        show [NodeIds]
        """
        current_time = self._tracker.current_time
        current_pos = self._tracker.current
        current_dir = self._pointer.current
        current_pathloss = self._pathloss_calc.current

        current_time_str = 'time: %.1f' % current_time
        print()
        print(current_time_str)
        print('-' * len(current_time_str))
        print()
        if arg:
            nodeidstr = arg.split()[0]
            print(current_pos.get_rows(self._tracker.nodeidstr_to_nodeidlist(nodeidstr)))
            print()
            if not current_dir.empty:
                print(current_dir.get_rows(self._pointer.nodeidstr_to_nodeidlist(nodeidstr)))
                print()
            if not current_pathloss.empty:
                print(current_pathloss.get_rows(self._pointer.nodeidstr_to_nodeidlist(nodeidstr)))
                print()
            if self._traffic_flows:
                print()
                print('flows')
                print('-----')
                print(' '.join(self._traffic_flows))
        else:
            print('location')
            print('--------')
            print(current_pos)
            print()
            if not current_dir.empty:
                print('pointing')
                print('--------')
                print(current_dir)
            if not current_pathloss.empty:
                print()
                print('pathloss')
                print('--------')
                print(current_pathloss.pathloss_table())
            if self._traffic_flows:
                print()
                print('flows')
                print('-----')
                print(' '.join(self._traffic_flows))
        print()



    def do_move(self, arg):
        """
        Move one or more Nodes [n]orth, [s]outh, [e]ast, [w]est
        [u]p or [d]own by 1 or more steps.

        move NodeIds n|s|e|w|u|d [steps]
        """
        toks = arg.split()

        nodeidlist = []

        try:
            nodeidlist = self._tracker.nodeidstr_to_nodeidlist(toks[0])
        except:
            self.do_help('move')
            return

        if not nodeidlist:
            print('No matching nodes found for %s.' % toks[0])
            return

        direction = toks[1].lower()

        if not direction in self._direction_handler:
            print('Undefined direction "%s".' % toks[1])
            return

        steps = 1 if len(toks) < 3 else int(toks[2])

        self._direction_handler[direction](nodeidlist, steps)
        self._send()


    def move_east(self, nodeidlist, steps):
        step = self._latlonstep * steps
        self._tracker.move_lon(nodeidlist, step)


    def move_west(self, nodeidlist, steps):
        step = -self._latlonstep * steps
        self._tracker.move_lon(nodeidlist, step)


    def move_north(self, nodeidlist, steps):
        step = self._latlonstep * steps
        self._tracker.move_lat(nodeidlist, step)


    def move_south(self, nodeidlist, steps):
        step = -self._latlonstep * steps
        self._tracker.move_lat(nodeidlist, step)


    def move_up(self, nodeidlist, steps):
        step = self._altstep * steps
        self._tracker.move_alt(nodeidlist, step)


    def move_down(self, nodeidlist, steps):
        step = -self._altstep * steps
        self._tracker.move_alt(nodeidlist, step)


    def do_moveto(self, arg):
        """
        Move one Node (src) to the position of another Node (dst).

        moveto srcNodeId dstNodeId
        """
        if len(arg) < 2:
            self.do_help('moveto')
            return

        toks = arg.split()

        srcnodes = []
        dstnodes = []

        try:
            srcnodes = self._tracker.nodeidstr_to_nodeidlist(toks[0])
            dstnodes = self._tracker.nodeidstr_to_nodeidlist(toks[1])
        except:
            self.do_help('moveto')
            return

        if not srcnodes:
            print('Unknown source "%s"' % toks[0])
            return

        if not dstnodes:
            print('Unknown destination "%s"' % toks[1])
            return

        if len(dstnodes) > 2:
            print('Too many destination nodes')
            return

        dstnode = dstnodes.pop()

        self._tracker.moveto(srcnodes, dstnode)
        self._send()


    def do_movewith(self, arg):
        """
        Set one or more Nodes (followers) to move with another Node (leader).

        movewith followerNodeIds leaderNodeId
        """
        if len(arg) < 2:
            self.do_help('movewith')
            return

        toks = arg.split()

        srcnodes = []
        dstnodes = []

        try:
            srcnodes = self._tracker.nodeidstr_to_nodeidlist(toks[0])
            dstnodes = self._tracker.nodeidstr_to_nodeidlist(toks[1])
        except:
            self.do_help('movewith')
            return

        if not srcnodes:
            print('Unknown source "%s"' % toks[0])
            return

        if not dstnodes:
            print('Unknown destination "%s"' % toks[1])
            return

        if len(dstnodes) > 2:
            print('Too many destination nodes')
            return

        dstnode = dstnodes.pop()

        self._tracker.movewith(srcnodes, dstnode)


    def do_azimuth(self, arg):
        """
        Adjust the azimuth component of one or more Nodes velocity
        vector [cw] clockwise or [cc] counterclockwise by one or more
        steps.

        azimuth NodeIds cw|cc [steps]
        """
        toks = arg.split()

        try:
            nodeidlist = self._tracker.nodeidstr_to_nodeidlist(toks[0])
        except:
            self.do_help('azimuth')
            return

        if not nodeidlist:
            print('No matching nodes found for %s.' % toks[0])
            return

        azimuth = toks[1].lower()

        if not azimuth in self._azimuth_handler:
            print('Unrecognized azimuth "%s".' % toks[1])
            return

        steps = 1 if len(toks) < 3 else int(toks[2])

        self._azimuth_handler[azimuth](nodeidlist, steps)
        self._send()


    def do_elevation(self, arg):
        """
        Adjust the elevation component of one or more Nodes velocity vector [u]p
        or [d]own by one or more steps.

        elevation NodeIds u|d [steps]
        """
        toks = arg.split()

        try:
            nodeidlist = self._tracker.nodeidstr_to_nodeidlist(toks[0])
        except:
            self.do_help('elevation')
            return

        if not nodeidlist:
            print('No matching nodes found for %s.' % toks[0])
            return

        elevation = toks[1].lower()

        if not elevation in self._elevation_handler:
            print('Unrecognized elevation "%s".' % toks[1])
            return

        steps = 1 if len(toks) < 3 else int(toks[2])

        self._elevation_handler[elevation](nodeidlist, steps)
        self._send()


    def do_point(self, arg):
        """
        Adjust antenna pointing of one or more nodes [u]p, [d]own, [cw] clockwise
        or [cc] counter clockwise by one or more steps.

        point NodeIds u|d|cw|cc [steps]
        """
        toks = arg.split()

        try:
            nodeidlist = self._pointer.nodeidstr_to_nodeidlist(toks[0])
        except:
            self.do_help('point')
            return

        if not nodeidlist:
            print('No antenna information found for node %s.' % toks[0])
            return

        pointing = toks[1].lower()

        if not pointing in self._pointing_handler:
            print('Undefined pointing "%s".' % toks[1])
            return

        steps = 1 if len(toks) < 3 else int(toks[2])

        self._pointing_handler[pointing](nodeidlist, steps)
        self._send()


    def elevation_up(self, nodeidlist, steps):
        step = self._anglestep * steps
        self._tracker.orient_elevation(nodeidlist, step)

    def elevation_down(self, nodeidlist, steps):
        step = -self._anglestep * steps
        self._tracker.orient_elevation(nodeidlist, step)

    def azimuth_clockwise(self, nodeidlist, steps):
        step = self._anglestep * steps
        self._tracker.orient_azimuth(nodeidlist, step)

    def azimuth_counter_clockwise(self, nodeidlist, steps):
        step = -self._anglestep * steps
        self._tracker.orient_azimuth(nodeidlist, step)


    def pitch_up(self, nodeidlist, steps):
        step = self._anglestep * steps
        self._tracker.pitch(nodeidlist, step)

    def pitch_down(self, nodeidlist, steps):
        step = -self._anglestep * steps
        self._tracker.pitch(nodeidlist, step)


    def roll_clockwise(self, nodeidlist, steps):
        step = self._anglestep * steps
        self._tracker.roll(nodeidlist, step)

    def roll_counter_clockwise(self, nodeidlist, steps):
        step = -self._anglestep * steps
        self._tracker.roll(nodeidlist, step)


    def yaw_clockwise(self, nodeidlist, steps):
        step = self._anglestep * steps
        self._tracker.yaw(nodeidlist, step)

    def yaw_counter_clockwise(self, nodeidlist, steps):
        step = -self._anglestep * steps
        self._tracker.yaw(nodeidlist, step)


    def point_up(self, nodeidlist, steps):
        step = self._anglestep * steps
        self._pointer.point_elevation(nodeidlist, step)

    def point_down(self, nodeidlist, steps):
        step = -self._anglestep * steps
        self._pointer.point_elevation(nodeidlist, step)

    def point_clockwise(self, nodeidlist, steps):
        step = self._anglestep * steps
        self._pointer.point_azimuth(nodeidlist, step)

    def point_counter_clockwise(self, nodeidlist, steps):
        step = -self._anglestep * steps
        self._pointer.point_azimuth(nodeidlist, step)


    def do_pitch(self, arg):
        """
        Adjust the pitch of one or more Nodes [u]p or [d]own
        by one or more steps.

        pitch NodeIds u|d [steps]
        """
        toks = arg.split()

        try:
            nodeidlist = self._tracker.nodeidstr_to_nodeidlist(toks[0])
        except:
            self.do_help('pitch')
            return

        if not nodeidlist:
            print('No matching nodes found for %s.' % toks[0])
            return

        direction = toks[1].lower()

        if not direction in self._pitch_handler:
            print('Undefined pitch direction "%s".' % toks[1])
            return

        steps = 1 if len(toks) < 3 else int(toks[2])

        self._pitch_handler[direction](nodeidlist, steps)
        self._send()


    def do_roll(self, arg):
        """
        Adjust the roll of one or more Nodes [cw] clockwise or [cc]
        counter-clockwise by one or more steps.

        roll NodeIds cw|cc [steps]
        """
        toks = arg.split()

        try:
            nodeidlist = self._tracker.nodeidstr_to_nodeidlist(toks[0])
        except:
            self.do_help('roll')
            return

        if not nodeidlist:
            print('No matching nodes found for %s.' % toks[0])
            return

        direction = toks[1].lower()

        if not direction in self._roll_handler:
            print('Undefined roll direction "%s".' % toks[1])
            return

        steps = 1 if len(toks) < 3 else int(toks[2])

        self._roll_handler[direction](nodeidlist, steps)
        self._send()


    def do_yaw(self, arg):
        """
        Adjust the yaw of one or more Nodes [cw] clockwise or [cc]
        counter-clockwise by one or more steps.

        yaw NodeIds cw|cc [steps]
        """
        toks = arg.split()

        try:
            nodeidlist = self._tracker.nodeidstr_to_nodeidlist(toks[0])
        except:
            self.do_help('yaw')
            return

        if not nodeidlist:
            print('No matching nodes found for %s.' % toks[0])
            return

        direction = toks[1].lower()

        if not direction in self._yaw_handler:
            print('Undefined yaw direction "%s".' % toks[1])
            return

        steps = 1 if len(toks) < 3 else int(toks[2])

        self._yaw_handler[direction](nodeidlist, steps)
        self._send()


    def do_select(self, arg):
        """
        Select the current antenna index for one or more Nodes.

        select NodeIds AntennaId
        """
        toks = arg.split()

        if not len(toks) == 2:
            self.do_help('select')
            return

        nodeidlist = []

        try:
            nodeidlist = self._pointer.nodeidstr_to_nodeidlist(toks[0])
        except:
            self.do_help('select')
            return

        if not nodeidlist:
            print('No matching nodes found for %s.' % toks[0])
            return

        try:
            ant_num = int(toks[1])
            self._pointer.select(nodeidlist, ant_num)
            self._send()
        except Exception as e:
            print(e)
            return


    def do_pointat(self, arg):
        """
        Point the antenna of one or more Nodes (src) at another Node
        (dst).  Make the selection sticky by adding literal "track" -
        when the dstNode moves, the srcNodes automatically update
        pointing to follow.

        pointat srcNodeIds dstNodeId [track]
        """
        toks = arg.split()

        if len(toks) < 2:
            self.do_help('pointat')
            return

        srcnodes = []
        dstnodes = []

        try:
            srcnodes = self._pointer.nodeidstr_to_nodeidlist(toks[0])
            dstnodes = self._tracker.nodeidstr_to_nodeidlist(toks[1])
        except:
            self.do_help('pointat')
            return

        if not srcnodes:
            print('No valid srcNodeIds in "%s"' % toks[0])
            return

        if not len(dstnodes) == 1:
            print('invalid dstNodeId argument "%s"' % toks[1])
            return

        dstnode = dstnodes.pop()

        track = False

        if len(toks) > 2:
            track = toks[2].lower() == 'track'

        self._pointer.point_at(srcnodes, dstnode, track)

        self._send()


    def do_write(self, arg):
        """
        Write the current Nodes state to the State File at the
        next timestep.

        write
        """
        if not self._statefd:
            self._statefd = open(self._statefile, 'w+')

        self._writer.write(self._writetime,
                           self._statefd,
                           self._tracker.current,
                           self._pointer.current)

        self._writetime += self._timestep


    def do_step(self, arg):
        """
        When launched with an EELFILE with more than one timepoint,
        step forward or backwards by one or more time steps. A positive
        timesteps value N move forward N state in the EEL file,
        a negative value moves backward in time.

        step [timesteps]
        """
        steps = 1

        toks = arg.split()

        if toks:
            try:
                steps = int(toks[0])
            except:
                print('Invalid step "%s"' % toks[0])
                return

        self._tracker.step(steps)

        self._pointer.step(steps)

        self._send()


    def do_flowon(self, arg):
        """
        Start traffic flows. When more than one src or dst is
        specified, multiple flows are started. The flows are
        associated with the specified name. The name must not match an
        active set of flows. No checks are made to verify the src or
        dst Ids are apropriate types to support the flows (for example
        to check that they are not jammers or spectrum monitor
        platforms).

        flowon name srcNodeIds dstNodeIds [proto=PROTO] [ttl=TTL] [tos=TOS] PATTERN

          PROTO: {udp,tcp,multicast}

          PATTERN: {PERIODIC,POISSON,JITTER}

          PERIODIC: periodic rate_msgs_per_second size_bytes

          POISSON: poisson average_rate_msgs_per_second size_bytes

          JITTER: jitter  rate_msgs_per_second size_bytes JITTER_FRACTION

          JITTER_FRACTION: [0.0 0.5]
        """
        toks = arg.split()

        if len(toks) < 5:
            self.do_help('flowon')
            return

        flow_name = toks[0]

        srcids = []
        dstids = []

        protocol = TrafficProtocolType.UDP

        tos = 0

        ttl = 1

        if flow_name in self._traffic_flows:
            print(f'Flow name "{flow_name}" is already active.')
            return

        toks.pop(0)

        try:
            srcids = self._pointer.nodeidstr_to_nodeidlist(toks[0])
            dstids = self._tracker.nodeidstr_to_nodeidlist(toks[1])
        except:
            self.do_help('flowon')
            return

        if not srcids:
            print('Unknown source "%s"' % toks[0])
            return

        if not dstids:
            print('Unknown destination "%s"' % toks[1])
            return

        sources = [self._tracker.id_to_node(id) for id in srcids]
        destinations = [self._tracker.id_to_node(id) for id in dstids]

        toks.pop(0)
        toks.pop(0)

        subtoks = list(map(lambda s: s.split('='), toks))

        subtoks.reverse()

        while len(subtoks[-1]) == 2:
            tname,tval = subtoks.pop()

            tname = tname.lower()
            print(f'tname={tname} tval={tval}')

            if tname == 'proto':
                protocol = {
                    'udp':TrafficProtocolType.UDP,
                    'tcp':TrafficProtocolType.TCP,
                    'multicast':TrafficProtocolType.MULTICAST
                }.get(tval.lower(), None)

                if not protocol:
                    print(f'Unknown flow_on protocol "{protocol}"')
                    return

            elif tname == 'tos':
                tos = int(tval)

            elif tname == 'ttl':
                ttl = int(tval)

            else:
                print(f'unknown flow_on specifier "{tname}"')
                return

        flowtypetok = subtoks.pop()[0]

        flowtype = {
            'periodic': SimpleTrafficFlowType.PERIODIC,
            'poisson': SimpleTrafficFlowType.POISSON,
            'jitter': SimpleTrafficFlowType.JITTER
        }.get(flowtypetok, None)

        if flowtype is None:
            print(f'unknown flow_on flow type "{flowtypetok}"')
            return

        packet_rate = float(subtoks.pop()[0])

        size_bytes = int(subtoks.pop()[0])

        jitter_fraction = 0.0

        if subtoks:
            jitter_fraction = float(subtoks.pop()[0])

        flow_on_request = \
            StartSimpleFlowRequest(flow_name,
                                   sources,
                                   destinations,
                                   protocol,
                                   tos,
                                   ttl,
                                   flowtype,
                                   size_bytes,
                                   packet_rate,
                                   jitter_fraction)

        self._publisher.publish_flow_on(flow_on_request)

        self._traffic_flows[flow_name] = arg


    def do_flowoff(self, arg):
        """
        Stop traffic flows. The name is as specified in the flowon command
        and stops all flows associated with it.

        flowoff name
        """
        toks = arg.split()

        if len(toks) < 1:
            self.do_help('flowoff')
            return

        flow_name = toks[0]

        if not flow_name in self._traffic_flows:
            print(f'Unknown flow name "{name}".')
            return

        flow_off_request = StopFlowRequest(flow_name, [], [], [])

        self._publisher.publish_flow_off(flow_off_request)

        self._traffic_flows.pop(flow_name)


    def do_jamon(self, arg):
        """
        Start jamming transmission from a jammer node. A jammer node only
        transmits a single pattern at a time; specifying a jamon command
        to the same jammer replaces the active pattern.

        jamon NodeId txpower_dBm bandwidth_hz period_usec DUTYCYCLE frequency_hz[,frequency_hz]*

          DUTYCYCLE: [0 100]
        """
        pass


    def do_jamoff(self, arg):
        """
        Stop jamming transmission from the specified Node.

        jamoff NodeId
        """
        pass
