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

from threading import Thread
import time
import traceback

import docker


class ContainerWorker(Thread):
    """Start and stop containers in a separate thread.

    Docker start and stop operations are long lasting calls.
    Handling them in the main emexd waveform_resource thread
    causes emexd to be unresponsive to clients while the
    operation lasts. Those operations are moved to this thread
    which exchanges input and output work items with the
    ContainerManager with the worker input queue (items from
    Manager to Worker) and worker output queue (return items
    from Worker to Manager).

    In order to maintain the main emexd thread as an event
    driven waveform resource thread, this thread writes
    a simple log message over a tcp socket (worker_socket)
    to the main thread to signal completion of a work item.
    """
    def __init__(self,
                 config,
                 docker_client,
                 worker_in_q,
                 worker_out_q,
                 worker_socket,
                 socket_lock):
        super().__init__()
        self._config = config
        self._dclient = docker_client
        self._worker_in_q = worker_in_q
        self._worker_out_q = worker_out_q
        self._worker_socket = worker_socket
        self._socket_lock = socket_lock
        self._start_seq = 1
        self._stop_seq = 1


    def run(self):
        loglevel = self._config.emexcontainerd_loglevel

        while True:
            item  = self._worker_in_q.get()

            command = item[0]

            if command == 'start':
                emoe_rt, cpus_str, ports, listenaddress, listenport = item[1:]

                try:
                    # start the container
                    container = self._dclient.containers.run(
                        image=self._config.docker_image,
                        name=emoe_rt.container_name,
                        privileged=True,
                        cpuset_cpus=cpus_str,
                        environment={'EMEXD_LISTEN_ADDRESS': listenaddress,
                                     'EMEXD_LISTEN_PORT': str(listenport),
                                     'EMOE_ID':emoe_rt.emoe_id},
                        volumes={f'{emoe_rt.workdir}':{'bind':'/tmp/etce', 'mode':'rw'}},
                        ports=ports,
                        detach=True,
                        command=f'/opt/run-emexcontainerd.sh -l {loglevel}')

                    # the start call didn't thrown an error, wait to confirm
                    # the container appears in the list of running containers
                    attempts = 10
                    found = False
                    while not found and attempts>0:
                        time.sleep(1)
                        for c in self._dclient.containers.list(all=True):
                            if c.name == emoe_rt.container_name:
                                found = True
                                break
                        attempts -= 1

                    if found:
                        self._worker_out_q.put(
                            ('start',True,'ok',emoe_rt,ports,container))
                    else:
                        message = \
                            f'Failed to find emoe container "{emoe_rt.container_name}" in list of ' \
                            f'running emoes after successful start.'

                        self._worker_out_q.put(
                            ('start',False,message,emoe_rt,ports,listenaddress,listenport))

                except docker.errors.APIError as e:
                    message = str(e)

                    self._worker_out_q.put(
                        ('start',False,message,emoe_rt,ports,listenaddress,listenport))

                except Exception as e:
                    message = str(e)

                    self._worker_out_q.put(
                        ('start',False,message,emoe_rt,ports,listenaddress,listenport))

                finally:
                    # signal the emexd event loop - doesn't really matter what we send
                    ret = f'start {self._start_seq} emoe "{emoe_rt.emoe.name}"'

                    with self._socket_lock:
                        self._worker_socket.send(bytes(ret,'utf-8'))

                    self._start_seq += 1

            else: # stop
                container = item[1]

                message = f'stop {self._stop_seq} {container.name} {container.status}'

                try:
                    if container.status.lower() in ('created', 'restarting', 'running'):
                        container.stop()

                        container.remove(force=True)

                        self._worker_out_q.put(('stop',True,message))

                    elif container.status.lower() in ('paused', 'exited'):
                        container.remove(force=True)

                        self._worker_out_q.put(('stop',True,message))

                    else:
                        message = \
                            f'stop {self._stop_seq} name:{container.name} ' \
                            f'state:{container.status}, ignoring stop.'

                        self._worker_out_q.put(('stop', False, message))

                except:
                    message = \
                        f'stop {self._stop_seq} {container.name} exception: ' \
                        f'{traceback.format_exc()}'

                    self._worker_out_q.put(('stop', False, message))

                with self._socket_lock:
                    self._worker_socket.send(bytes(message,'utf-8'))

                self._stop_seq += 1
