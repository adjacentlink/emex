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
import json
import select
import socket
import threading

from queue import Queue
from emex.utils import sock_send_string


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


class JsonServer:
    def __init__(self, client_endpoint, verbose, orientation):
        client_address,client_port = client_endpoint.split(':')
        self._client_endpoint = (client_address, int(client_port))
        self._orientation = orientation

        self._verbose = verbose
        self._broker_sock_read = None
        self._broker_sock_write = None
        self._client_sock = None
        self._epoll = None
        self._connections = {}
        self._client_num = 1
        self._socket_names = {}

        self._open()

        self._thread = threading.Thread(target=self.send_dataframes)
        self._thread.setDaemon(True)
        self._thread.start()


    def _open(self):
        if self._client_sock:
            return

        self._epoll = select.epoll()

        self._client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._client_sock.bind(self._client_endpoint)
        self._client_sock.listen(1)
        self._client_sock.setblocking(0)
        self._epoll.register(self._client_sock.fileno(), select.POLLIN)

        self._broker_endpoint = ('127.0.0.1', 47355)
        self._broker_sock_read = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._broker_sock_read.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._broker_sock_read.bind(self._broker_endpoint)
        self._broker_sock_read.listen(1)
        self._broker_sock_read.setblocking(0)
        self._epoll.register(self._broker_sock_read.fileno(), select.POLLIN)

        self._q = Queue()
        self._connections = {}
        self._writer_conn = None

        self._socket_names = {
            self._client_sock.fileno():'client_sock',
            self._broker_sock_read.fileno():'broker_sock_read'
        }

        self._broker_sock_write = None


    def _event_name(self, eventno):
        return eventstrs.get(eventno, 'UNKNOWN')


    def join(self):
        self._thread.join()


    def dfs_to_json_bytestr(self, dfs):
        dfs_dict = {}

        for name,df in dfs.items():
            dfs_dict[name] = df.to_dict(self._orientation)

        return bytes(json.dumps(dfs_dict), 'utf-8')


    def process_dataframes(self, timestamp, dfs):
        logging.info(f'process_dataframes {timestamp}')

        if not self._broker_sock_write:
            self._broker_sock_write = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            self._broker_sock_write.connect(self._broker_endpoint)

        self._q.put((timestamp,dfs))

        timestamp_string = f'{timestamp}'

        self._broker_sock_write.sendall(bytes(timestamp_string, 'utf-8'))


    def send_dataframes(self):
        try:
            while True:
                events = self._epoll.poll()

                logging.debug('poll')

                for fileno,event in events:
                    logging.debug(f'{self._socket_names.get(fileno, fileno)}, {self._event_name(event)}')

                    if fileno == self._client_sock.fileno():
                        conn,addr = self._client_sock.accept()
                        conn.setblocking(0)
                        self._epoll.register(conn.fileno(), select.EPOLLIN)
                        self._connections[conn.fileno()] = conn
                        self._socket_names[conn.fileno()] = f'client{self._client_num}'
                        self._client_num+=1
                        logging.info(f'connect {fileno} {self._socket_names[conn.fileno()]}')

                    elif fileno == self._broker_sock_read.fileno():
                        if self._writer_conn:
                            logging.info('unexpected read on broker_sock')
                        else:
                            logging.info('open writer_conn start')

                            self._writer_conn,_ = self._broker_sock_read.accept()
                            self._writer_conn.setblocking(0)
                            self._epoll.register(self._writer_conn.fileno(), select.EPOLLIN)
                            self._socket_names[self._writer_conn.fileno()] = 'writer_conn'

                    elif fileno == self._writer_conn.fileno():
                        logging.debug('do read writer_conn')
                        _ = self._writer_conn.recv(65535)
                        while not self._q.empty():
                            timestamp,dfs = self._q.get()
                            df_json_bytestr = self.dfs_to_json_bytestr(dfs)
                            for _,conn in self._connections.items():
                                logging.debug(f'send ts={timestamp} len={len(df_json_bytestr)} '
                                              f'type={type(df_json_bytestr)}')
                                sock_send_string(conn, df_json_bytestr)

                    elif event & select.EPOLLHUP:
                        logging.info(f'EPOLLHUP {fileno}')
                        self._epoll.unregister(fileno)
                        if fileno in self._connections:
                            self._connections[fileno].close()
                            del self._connections[fileno]

                    elif event & select.EPOLLIN and fileno in self._connections:
                        logging.info(f'unregister {fileno}')
                        self._epoll.unregister(fileno)
                        self._connections[fileno].close()
                        del self._connections[fileno]

                    else:
                        logging.debug(f'unhandled: {self._socket_names.get(fileno, fileno)}, '
                                      f'{self._event_name(event)}')

        except Exception as e:
            logging.error(f'Exception: {e}')

        finally:
            self.close()


    def close(self):
        logging.info('close start')
        self._epoll.unregister(self._client_sock.fileno())
        self._epoll.unregister(self._broker_sock_read.fileno())
        for fileno,conn in self._connections.items():
            self._epoll.unregister(fileno)
            conn.close()

        if self._writer_conn:
            self._epoll.unregister(self._writer_conn.fileno())
            self._writer_conn.close()

        self._epoll.close()
        self._client_sock.close()
        self._broker_sock_read.close()
        logging.info('close end')
