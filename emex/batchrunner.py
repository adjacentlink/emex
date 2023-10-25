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
import logging
import os
import select
import socket
import threading
import time

from emex.emoe import Emoe
from emex.emoestate import EmoeState
from emex.emexdclientmessagehandler import EmexdClientMessageHandler
from emex.scenariorpcclient import ScenarioRpcClient
from emex.eventsequencer import EventSequencer
from emex.utils import sock_send_string,sock_recv_string
from emex.yamlscenariobuilder import YamlScenarioBuilder
from emex.emexdmessages import (
    ServiceAccessor,
    CheckEmoeReply,
    StartEmoeReply,
    StopEmoeReply,
    ListEmoesReply,
    ListEmoesReplyEntry,
    EmoeStateTransitionEvent
)
from emex.monitors.emex import Emex


eventstrs = {
    select.EPOLLIN:'EPOLLIN',
    select.EPOLLOUT:'EPOLLOUT',
    select.EPOLLPRI:'EPOLLPRI',
    select.EPOLLERR:'EPOLLERR',
    select.EPOLLHUP:'EPOLLHUP',
    select.EPOLLET:'EPOLLET',
    select.EPOLLONESHOT:'EPOLLONESHOT',
    select.EPOLLEXCLUSIVE:'EPOLLEXCLUSIVE',
    select.EPOLLRDHUP:'EPOLLRDHUP',
    select.EPOLLRDNORM:'EPOLLRDNORM',
    select.EPOLLRDBAND:'EPOLLRDBAND',
    select.EPOLLWRNORM:'EPOLLWRNORM',
    select.EPOLLWRBAND:'EPOLLWRBAND',
    select.EPOLLMSG:'EPOLLMSG'
}


class ScenarioThread(threading.Thread):
    def __init__(self, emoe_name, emoe_endpoint, events, monitor=None):
        super().__init__()
        self._emoe_name = emoe_name
        self._emoe_endpoint = emoe_endpoint
        self._events = events
        self._flows_df = []
        self._monitor = monitor
        self._log = f'scenario_thread: initialized'
        self._scenario_rpc = None
        self._interrupted = False
        self._rport = self._emoe_endpoint[1]
        self._laddr = None
        self._lport = None

    @property
    def log(self):
        return self._log


    def run(self):
        # connect and issue events
        self._log = f'connect to {self._emoe_endpoint}'

        self._scenario_rpc = ScenarioRpcClient(self._emoe_endpoint)

        self._laddr,self._lport = self._scenario_rpc.getsockname()

        # send a StartFlowsRequest for all flows
        sequencer = EventSequencer(self._events)

        event_num = 0
        num_events = sequencer.num_events

        ok = False,
        message = None
        self._flows_df = []

        self._log = f'lport:{self._lport}, rport:{self._rport}, started'

        for eventtime,eventdict in sequencer:
            self._log = \
                f'lport:{self._lport}, rport:{self._rport}, ' \
                f'process:   {event_num:3d} of {num_events:3d} events, eventtime:{eventtime:4.1f}'

            if self._interrupted:
                self._log = f'lport:{self._lport}, rport:{self._rport}, interrupted'
                break

            try:
                ok,message,self._flows_df = self._scenario_rpc.send_event(eventdict)

            except Exception as e:
                self._log = f'lport:{self._lport}, rport:{self._rport}, EXCEPTION {e}'
                return

            self._log = \
                f'lport:{self._lport}, rport:{self._rport}, ' \
                f'processed: {event_num:3d} of {num_events:3d} events, eventtime:{eventtime:4.1f}'

            event_num += 1

        self._log = f'lport:{self._lport}, rport:{self._rport}, stopped'


    def cleanup(self):
        if not self._interrupted:
            self._interrupted = True

            if self._monitor:
                self._log = f'{self._emoe_name} scenario thread: stop monitor'

                self._monitor.stop(self._flows_df)

            if self._scenario_rpc:
                self._scenario_rpc.close()


class BatchRunner:
    def __init__(self, args):
        self._emexd_endpoint = (args.address, args.port)

        self._output_path_root = args.output_path
        self._run_monitor = args.monitor
        self._numtrials = args.numtrials

        self._scenario_builders = [YamlScenarioBuilder(sf) for sf in args.scenariofiles]

        name_counts = defaultdict(lambda: 0)

        for sb in self._scenario_builders:
            name_counts[sb.name] += 1

        for name,count in name_counts.items():
            if count > 1:
                logging.error(f'Found duplicate scenario name "{name}". Quitting.')
                exit(4)

        self._ants_plats_ics = []

        logging.info(f'Running from scenariofiles:')
        for num,sf in enumerate(args.scenariofiles, start=1):
            logging.info(f'{num:2}: {sf}')

        # track the next scenario to be started. scenarios are run in order
        # of the yml files specified on the command line and each is run
        # numtrials times. there is no attempt to run scenarios in a different
        # order than specified (for now) - for example if a scenario specified
        # later in the order uses fewer CPUs and could be attempted sooner.
        self._scenario_index = 0
        self._total_trials = self._numtrials * len(self._scenario_builders)
        self._stop_timer = False
        self._done_running = False

        logging.info(f'Will run {self._numtrials} trials each for {len(self._scenario_builders)} '
                     f'scenarios, {self._total_trials} total emulations.')

        # collection of locally known emoes by state
        self._emoes_dict = {}

        # request these from emexd at startup, needed to build emoes
        self._antennatypes = None
        self._platformtypes = None

        self._trials = args.numtrials

        self._message_handler = EmexdClientMessageHandler()

        self._timer_endpoint = ('127.0.0.1', 47358)
        self._timer_listen_sock = None
        self._timer_write_sock = None
        self._epoll = None
        self._open()

        self._thread = threading.Thread(target=self._do_tests)
        self._thread.setDaemon(True)
        self._thread.start()


    def _open(self):
        if self._timer_listen_sock:
            return

        self._epoll = select.epoll()

        self._timer_conn = None

        # Listen for timer
        self._timer_listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._timer_listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._timer_listen_sock.bind(self._timer_endpoint)
        self._timer_listen_sock.listen(1)
        self._timer_listen_sock.setblocking(0)

        # connect to emexd
        self._epoll.register(self._timer_listen_sock.fileno(), select.POLLIN)
        self._emexd_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._emexd_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._emexd_sock.connect(self._emexd_endpoint)
        self._emexd_sock.setblocking(0)

        # register sockets
        self._epoll = select.epoll()
        self._epoll.register(self._timer_listen_sock.fileno(), select.POLLIN)
        self._epoll.register(self._emexd_sock.fileno(), select.POLLIN)

        self._socket_names = {
            self._emexd_sock.fileno():'emexd_sock',
            self._timer_listen_sock.fileno():'timer_listen_sock'
        }


    def process_emoe_list(self, reply):
        """Parse the listEmoesReply message and update local state.

        The listEmoeReply message contains state information for all Emoes
        currently handled/known by emexd for this client. Process the list
        the local list of starting and running Emoes mirrors the emexd
        reported ones.

           1. The set of locally known Emoes == Emoes in the reply
           2. The state of each locally known Emoe is updated to match
              the emexd reported state.

              * Local Emoe is moved from the starting to running set if
                the reply reports its state as RUNNING
              * Local Emoe is moved from the starting to stopping state
                if the reply reports the state is STOPPING or greater,
                or not reported at all.

        Args:
           reply: a listEmoeReply instance
        """
        logging.info(f'rx listemoes entries:{len(reply.emoe_entries)} '
                     f'total_cpus:{reply.total_cpus} '
                     f'available_cpus:{reply.available_cpus}')

        processed_emoes = set([])

        for num_entry,entry in enumerate(reply.emoe_entries, start=1):
            """
            ListEmoesReplyEntry = \
                namedtuple('ListEmoesReplyEntry',
                           ['handle','emoe_name','state','cpus','service_accessors'])
            """
            processed_emoes.add(entry.emoe_name)

            emoe_cookie = self._emoes_dict.get(entry.emoe_name, None)

            if emoe_cookie is None:
                logging.error(f'None cookies for entry={entry}, Ignoring')
                continue

            local_entry,runner,builder,monitor = emoe_cookie

            if not local_entry and not runner:
                # this is the first report for this emoe, add the entry
                logging.info(f'{num_entry:3} emoe:{entry.emoe_name} state:{entry.state.name}')

                logging.debug(f'adding2 {entry.emoe_name} to emoes_dict')
                self._emoes_dict[entry.emoe_name] = (entry,runner,builder,monitor)

            elif entry == local_entry:
                if entry.state == EmoeState.RUNNING:
                    logging.info(f'{num_entry:3} emoe:{entry.emoe_name} state:{entry.state.name}  '
                                 f'eventlog: {runner.log}  is_alive:{runner.is_alive()}')

                    # for a continued RUNNING state, stop the emoe when the scenario thread ends
                    if not runner.is_alive():
                        logging.info(f'stopping emoe {entry.emoe_name}')
                        runner.cleanup()
                        runner.join()
                        sock_send_string(self._emexd_sock,
                                         self._message_handler.build_stop_emoe_request_message(entry.handle))

                else:
                    logging.info(f'{num_entry:3} emoe:{entry.emoe_name} state:{entry.state.name}')

                continue

            if entry.state > EmoeState.RUNNING:
                logging.info(f'emoe {entry.emoe_name} transitioned to state {entry.state.name}')

            elif entry.state == EmoeState.RUNNING:
                logging.info(f'emoe {entry.emoe_name} transitioned to state {entry.state.name}')

                emoe_endpoint,otestpoint_endpoint = self._get_endpoints(entry.service_accessors)

                logging.info(f'emoe {entry.emoe_name} endpoints emoe:{emoe_endpoint} otestpoint:{otestpoint_endpoint}')

                if monitor and otestpoint_endpoint:
                    output_path = \
                        os.path.join(self._output_path_root, f'{entry.handle}.{entry.emoe_name}')
                    os.makedirs(output_path, exist_ok=True)

                    monitor.run(output_path, otestpoint_endpoint)

                runner = ScenarioThread(entry.emoe_name, emoe_endpoint, builder.events, monitor)
                runner.setDaemon(True)
                runner.start()

                logging.info(f'started {entry.emoe_name} events thread')


            elif entry.state > EmoeState.QUEUED:
                logging.info(f'emoe {entry.emoe_name} transitioned to state {entry.state.name}')

            # update the local state
            self._emoes_dict[entry.emoe_name] = (entry,runner,builder,monitor)

        unreported_emoes = set(self._emoes_dict).difference(processed_emoes)

        for emoe_name in unreported_emoes:
            local_entry,runner,builder,monitor = self._emoes_dict.pop(emoe_name)

            logging.info(f'"{emoe_name}" is complete')



    def bump_index(self):
        self._scenario_index = min(self._total_trials, self._scenario_index + 1)

        logging.debug(f'bump_index scenario_index: {self._scenario_index}')


    @property
    def done_starting(self):
        return self._scenario_index >= self._total_trials


    def index_trial(self, bump=False):
        if bump:
            self.bump_index()

        index = self._scenario_index // self._numtrials

        trial = self._scenario_index % self._numtrials

        logging.debug(f'index={index}, trial={trial}')

        return index,trial


    def next_emoe_name(self):
        logging.debug(f'next_emoe_name enter {self._scenario_index}')
        if self.done_starting:
            logging.debug(f'next_emoe_name exit {self._scenario_index} None')
            return None

        # name emoes as scenario_name-trial+1. Find the next emoe name
        # that isn't already started.
        index,trial = self.index_trial()

        scenario_name = self._scenario_builders[index].name

        emoe_name = f'{scenario_name}.{(trial+1):03}'

        while not self.done_starting and emoe_name in self._emoes_dict:
            logging.debug(f'next_emoe_name: {emoe_name} already used')

            index,trial = self.index_trial(bump=True)

            if index < len(self._scenario_builders):
                scenario_name = self._scenario_builders[index].name

                emoe_name = f'{scenario_name}.{(trial+1):03}'

        if self.done_starting:
            logging.debug(f'next_emoe_name exit {self._scenario_index} None')

            return None

        logging.debug(f'next_emoe_name exit {self._scenario_index} {emoe_name}')

        return emoe_name


    def start_next_emoe(self, reply):
        if not self._ants_plats_ics:
            # cannot build emoes until model types are retrieved
            # from emexd
            return

        emoe_name = self.next_emoe_name()

        logging.debug(f'next emoe is {emoe_name}')
        if not emoe_name:
            return

        index,_ = self.index_trial()

        platforms,antennas,initial_conditions = self._ants_plats_ics[index]

        builder = self._scenario_builders[index]

        emoe = Emoe(emoe_name,
                    platforms=platforms,
                    antennas=antennas,
                    initial_conditions=initial_conditions)

        if emoe.cpus > reply.total_cpus:
            logging.error(f'Cannot support {emoe_name} that requires {emoe.cpus} CPUs but '
                          f'only {reply.total_cpus} total CPUs allocated to the server, skipping.')

            self.bump_index()

            return

        if emoe.cpus > reply.available_cpus:
            # not enough cpus right now
            return

        sock_send_string(self._emexd_sock,
                         self._message_handler.build_start_emoe_request_message(emoe))

        monitor = Emex(emoe) if self._run_monitor else None

        logging.debug(f'adding1 {emoe_name} to emoes_dict')
        self._emoes_dict[emoe_name] = (None,None,builder,monitor)


    def _get_endpoints(self, accessors):
        otestpoint_endpoint = None

        emoe_endpoint = None

        for accessor in accessors:
            if accessor.name == 'emexcontainerd':
                emoe_endpoint = (accessor.ip_address, accessor.port)

            elif accessor.name == 'otestpoint-publish':
                otestpoint_endpoint = (accessor.ip_address, accessor.port)

        return emoe_endpoint,otestpoint_endpoint


    def _event_name(self, eventno):
        return eventstrs.get(eventno, 'UNKNOWN')


    def do_stop(self, signum, frame):
        self._stop_timer = True


    def run(self, intervaltime_secs=1):
        self._timer_write_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._timer_write_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._timer_write_sock.connect(self._timer_endpoint)
        self._timer_write_sock.setblocking(0)

        elapsed_time = 0

        while not self._stop_timer:
            time.sleep(intervaltime_secs)

            elapsed_time += intervaltime_secs

            sock_send_string(self._timer_write_sock, bytes(str(elapsed_time), 'utf-8'))


    def _do_tests(self):
        """
        run the epoll loop and state machine - the goal is to keep emexd
        as full as possible running emoes, filling it up with as many
        as it will accept on startup and then immediately adding a new
        one whenever an existing emoe stops.

        emoes are added asynchronously - need to break up scenario runner to
        get access to the messagng

        1. track cpus available
        2. track state of submitted emoes
        3. remove emoes that are reported stopped
        4. remove emoes that timeout in some funky state
        5. heartbeat listemoes on an interval of 5 seconds
        6. on emoe removal run the next one as soon as there are enough resources

        need a threadpool to run the events - on first go, just stop emoes after a certain period,
        add a count that gets decremented on each listemoes
        """
        try:
            # request models at start
            sock_send_string(self._emexd_sock,
                             self._message_handler.build_models_request_message())

            while not self._done_running:
                events = self._epoll.poll()

                logging.debug('poll')

                for fileno,event in events:
                    logging.debug(f'{self._socket_names.get(fileno, fileno)}, {self._event_name(event)}')

                    if fileno == self._timer_listen_sock.fileno():
                        # accept timer connection
                        conn,addr = self._timer_listen_sock.accept()
                        conn.setblocking(0)
                        self._epoll.register(conn.fileno(), select.EPOLLIN)
                        self._socket_names[conn] = f'timer_conn'
                        logging.debug(f'connect {fileno} {self._socket_names[conn]}')
                        self._timer_conn = conn

                    elif fileno == self._emexd_sock.fileno():
                        # receive message from emexd
                        logging.debug('receive emexd message')

                        reply_str = sock_recv_string(self._emexd_sock)

                        reply = self._message_handler.parse_reply(reply_str)

                        if not reply:
                            logging.error(f'Unknown, empty reply')
                            return

                        if isinstance(reply, ListEmoesReply):
                            logging.debug(f'rx listemoes {reply}')

                            # process emoes list, stop emoe and start others
                            # send a request
                            self.process_emoe_list(reply)

                            # if all of the emoes have been started and there are no
                            # more entries from emexd then it is time to quit
                            if self.done_starting and not reply.emoe_entries:
                                self._done_running = True
                            else:
                                # try to start the next emoe
                                self.start_next_emoe(reply)

                        elif isinstance(reply, StartEmoeReply):
                            logging.debug(f'rx startemoes {reply.emoe_name} {reply.result}')

                            # check for failure
                            if not reply.result:
                                logging.error(f'emoe "{reply.emoe_name}" failed to start with error "{reply.message}"')
                                self._emoes_dict.pop(reply.emoe_name)

                                self.bump_index()

                        elif isinstance(reply, StopEmoeReply):
                            logging.debug(f'rx stopemoes {reply.emoe_name} {reply.result}')

                        elif isinstance(reply, EmoeStateTransitionEvent):
                            # just report this, they'll only be seen if emexd state-messages
                            # parameter is set to true, but we ignore them opting to
                            # keep track of emoes by poling
                            logging.debug(f'rx state transition {reply.emoe_name} {reply.state.name}')

                        elif isinstance(reply, tuple):
                            logging.debug(f'tuple type {type(reply)}')
                            self._antennatypes, self._platformtypes = reply

                            if not self._ants_plats_ics:
                                for builder in self._scenario_builders:
                                    self._ants_plats_ics.append(
                                        builder.build(self._platformtypes, self._antennatypes))


                    elif fileno == self._timer_conn.fileno():
                        # receive timer
                        message_str = sock_recv_string(self._timer_conn)
                        logging.debug(f'timer={message_str}')

                        # update stuff
                        sock_send_string(self._emexd_sock,
                                         self._message_handler.build_list_emoes_request_message())


                    elif event & select.EPOLLHUP:
                        logging.info(f'EPOLLHUP {fileno}')
                        self._epoll.unregister(fileno)
                        if fileno == self._timer_conn:
                            self._timer_conn.close()

                    else:
                        logging.debug(f'unhandled: {self._socket_names.get(fileno, fileno)}, '
                                      f'{self._event_name(event)}')

        #except Exception as e:
        #    logging.error(f'Exception: {e}')

        finally:
            self._stop_timer = True
            self.close()


    def close(self):
        for _,runner,_,_ in self._emoes_dict.values():
            runner.cleanup()

        logging.info('close start')
        self._epoll.unregister(self._timer_listen_sock.fileno())
        self._epoll.unregister(self._emexd_sock.fileno())

        if self._timer_conn:
            self._timer_conn.close()

        self._epoll.close()
        self._timer_listen_sock.close()
        self._emexd_sock.close()
        logging.info('close end')
