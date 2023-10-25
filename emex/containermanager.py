# Copyright (c) 2022,2023 - Adjacent Link LLC, Bridgewater, New Jersey
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


from queue import Queue
import re
import socket

import docker
import logging
import traceback

from emex.containerworker import ContainerWorker


class ContainerManager:
    def __init__(self, config, manager, host_port_manager, container_worker_connect_endpoint):
        self._dclient = docker.from_env()

        self._config = config

        self._manager = manager

        self._hpm = host_port_manager

        self._dclient.images.get(self._config.docker_image)

        self._worker_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        logging.info(f'Connecting container worker socket to {container_worker_connect_endpoint}')

        self._worker_socket.connect(container_worker_connect_endpoint)

        self._worker_in_q = Queue()
        self._worker_out_q = Queue()

        self._thread = \
            ContainerWorker(config,
                            self._dclient,
                            self._hpm,
                            self._worker_socket,
                            self._worker_in_q,
                            self._worker_out_q)

        self._thread.setName('thread_worker')
        self._thread.setDaemon(True)
        self._thread.start()


    def start(self, emoe_rt, listenaddress, listenport):
        # docker container run --privileged -it \
        #    --volume ${emoe_rt.workdir}:/tmp/etce \
        #    rockylinux.emexdev /opt/run.sh -d ${delaysecs}

        cpus_str = ','.join(map(str, emoe_rt.cpus))

        logging.info(f'Starting EMOE {emoe_rt.emoe.name} container {emoe_rt.container_name}')

        ports = {}

        # allocated availble host ports to map to container
        # port services that must have accessible to clients
        num_container_ports = len(emoe_rt.container_ports)

        if num_container_ports > self._hpm.num_available:
            message = \
                f'Cannot allocate emoe: {num_container_ports} ports required but ' \
                f'only {self._hpm.num_available} available.'

            logging.error(message)

            return (False,message)

        allocated_ports = self._hpm.allocate(num_container_ports)

        for host_port,(service_name,container_port) in \
            zip(allocated_ports, emoe_rt.container_ports.items()):

            emoe_rt.add_host_port_mapping(host_port, service_name)

            ports[container_port] = host_port

        logging.debug(f'queue put start {emoe_rt.emoe.name}')

        self._worker_in_q.put(
            ('start', emoe_rt, cpus_str, ports, listenaddress, listenport))

        return (True,'ok')


    def handle_container_worker_event(self, data):
        ret = str(data, 'utf-8')
        logging.info(f'handle_container_worker_event {ret}')

        while not self._worker_out_q.empty():
            item = self._worker_out_q.get()

            op,ok = item[:2]

            if op == 'start':
                if ok:
                    message,emoe_rt,ports,container = item[2:]

                    self._manager.register_started_container(emoe_rt, container)

                else:
                    message,emoe_rt,ports,listenaddress,listenport = item[2:]

                    logging.error(message)

                    emoe_rt.clear_host_port_mappings()

                    self._hpm.deallocate(ports.values())

                    # right now, assume port collision is the only reason for
                    # error and try to handl
                    if not self._handle_port_collision(message,
                                                       emoe_rt,
                                                       ports.values()):
                        logging.info('Container start failure does not appear to be a port collision.')

                    if emoe_rt.can_start():
                        # try again
                        self.start(emoe_rt, listenaddress, listenport)
                    else:
                        # exhausted attempts, send FAILED state message
                        self._manager.handle_failed_container_start(emoe_rt)

            else: # stop
                message = item[2]

                logging.info(message)


    def stop_and_remove(self, container):
        if not container:
            logger.error('ContainerManager stop_and_remove called with "None" '
                         'container. Ignoring.')

            return

        self._worker_in_q.put(('stop', container))

        logging.debug(f'queue put stop  {container.name}')

        logging.info(f'stopping EMOE container {container.name}')


    def stop_all_emex_containers(self):
        containers = self._dclient.containers.list(all=True)

        for c in containers:
            if c.image.tags:
                if self._config.docker_image in c.image.tags[0].split()[0]:
                    self.stop_and_remove(c)


    def stop_all_emex_containers_synchronous(self):
        containers = self._dclient.containers.list(all=True)

        for c in containers:
            if c.image.tags:
                if self._config.docker_image in c.image.tags[0].split()[0]:

                    try:
                        if c.status.lower() in ('created', 'running'):
                            logging.info(f'stop and remove container {c.name} state:{c.status}')

                            c.stop()

                            logging.debug(f'stop container 2 {c.name} {c.status}')

                            c.remove(force=True)

                            logging.debug(f'stop container 3 {c.name} {c.status}')

                    except:
                        logging.error('In ContainerManager.stop_all_emex_containers_synchronous:')

                        logging.error(traceback.format_exc())


    def _handle_port_collision(self, message, emoe_rt, allocated_ports):
        """
        Handle port already bound error. These two messages have been reported in the wild

          "Internal Server Error ("driver failed programming external connectivity on
           endpoint EMOENAME (...): Error starting userland proxy: listen tcp4 0.0.0.0:9001:
           bind: address already in use"

          "ERROR: 500 Server Error: Internal Server Error ("driver failed programming external
           connectivity on endpoint emoe2 (8f68a946...)
           : Bind for 0.0.0.0:9004 failed: port is already allocated")

        1. Try to extract the colliding port number from the message and exclude it
           from the resource pool
        2. If not, exclude all of the ports that were attempted to be allocated
        """

        # stop and remove the container - it was partially started
        for container in self._dclient.containers.list(all=True):
            if container.name == emoe_rt.container_name:
                self.stop_and_remove(container)

        # exclude the collided port if you can find it in the error message
        m1 = re.match(r'.*\d+\.\d+\.\d+\.\d+:(?P<port>\d+): bind: address already in use', message)
        m2 = re.match(f'.*\d+\.\d+\.\d+\.\d+:(?P<port>\d+) failed: port is already allocated', message)

        port_error = False

        if m1:
            port = int(m1.groupdict()['port'])
            self._hpm.exclude(port)
            port_error = True
        elif m2:
            port = int(m2.groupdict()['port'])
            self._hpm.exclude(port)
            port_error = True
        elif 'port' in message.lower() or 'bind' in message.lower():
            # if we can't extract the exact port, exclude them all
            for port in allocated_ports:
                self._hpm.exclude(port)
            port_error = True

        return port_error
