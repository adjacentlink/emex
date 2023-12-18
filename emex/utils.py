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

from collections import defaultdict,namedtuple
import importlib
import os
import pkgutil
import socket
import struct
import logging

import emex.data


def line_breaker(line, width):
    """
    break string line into multiple lines of width long
    """
    toks = line.split()

    toks.reverse()

    lines = []

    while toks:
        line = ''
        while len(line) < width and toks:
            line += toks.pop() + ' '
        lines.append(line)

    return lines


def configstrtoval(val, argtype=None):
    valstr = str(val)

    if argtype:
        if argtype == 'string':
            return str(valstr)
        elif argtype == 'bool':
            return bool(valstr)
        elif argtype == 'int':
            return int(valstr)
        elif argtype == 'float':
            return float(valstr)
        else:
            raise ValueError('Unknown explicit argtype "%s" '
                             'for conversion of "%s". Quitting.' %
                             (argtype, valstr))

    # float
    try:
        if '.' in valstr:
            result = float(valstr)
            return result
    except ValueError:
        pass
    #int
    try:
        result = int(valstr)
        return result
    except ValueError:
        pass
    # boolean
    if valstr.upper() == 'TRUE':
        return True
    if valstr.upper() == 'FALSE':
        return False
    # string
    return valstr


def group_components_by_label(platforms, label):
    """
    Logic to infer which waveform instances belong to
    a particular wireless network. Instances in the same
    network are assigned unique IP addresses but with
    common subnet address.

    Waveform instances are split in a two-tiered hierarchy:
    1. by waveform type
    2. by (optional) "net" label assigned to the instance

    All instances of the same waveform type are assumed to be in
    the same subnet unless they are further differentiated by
    a net label - a label with prefix 'net' (ie. net1, net-73, net_40).
    Instances with identical labels are assumed to be in a separate
    subnet and are assigned unique ip addresses within the subnet
    and differentiated from all other nodes.
    """
    component_groups = defaultdict(lambda: [])

    for platform in platforms:
        for component in platform.components:
            # waveform type is the first token in the waveform name
            wftype = component.emex_type_value.split('.')[0]

            # look for any label that starts with "net"
            net_labels = frozenset([l for l in component.labels
                                    if l.lower().startswith(label)])

            # partition ipv4_address components by waveform type
            # and network labels
            component_groups[(wftype, net_labels)].append((platform, component))

    return component_groups


def numstr_to_numlist(num_str):
    nums = []

    if not num_str:
        return nums

    if len(num_str.strip()) == 0:
        return nums

    numranges = num_str.split(',')

    for numrange in numranges:
        endpoints = numrange.split('-')

        startendpoint = int(endpoints[0])

        stopendpoint = int(endpoints[-1])

        newnums = []

        if startendpoint > stopendpoint:
            newnums = [i for i in range(startendpoint, stopendpoint-1, -1)]
        else:
            newnums = [i for i in range(startendpoint, stopendpoint+1)]

        for i in newnums:
            if not i in nums:
                nums.append(i)

    return nums


def load_class_from_modulename(modulename):
    """
    Search for a class with the same classname as the module.
    Capitalization doesn't matter. If there are more than one class
    definitions with the module name, but differeing only by capitalization,
    then not well defined which one will be instantiated
    """
    module = None

    try:
        module = importlib.import_module(modulename)
    except ModuleNotFoundError as e:
        return None

    basename = module.__name__.split('.')[-1]

    candidateclassname = basename.upper()

    try:
        for key in module.__dict__:
            if key.upper() == candidateclassname:
                candidateclass = module.__dict__[key]

                if callable(candidateclass):
                    return candidateclass

    except KeyError:
        return None

    return None


def load_platform_helpers(platforms):
    waveforms = set([])

    for plt in platforms:
        for c in plt.components:
            if c.emex_type == 'waveform':
                waveform = c.emex_type_value.split('.')[0]

                waveforms.add(waveform)

    # always load physical layer helper
    platform_helpers = [
        load_class_from_modulename(f'emex.helpers.platforms.phyhelper')
    ]

    for w in waveforms:
        wf_class = load_class_from_modulename(f'emex.helpers.platforms.{w}')

        if wf_class:
            platform_helpers.append(wf_class)

    return platform_helpers


def load_monitor(monitor_name):
    emex_monitors_mod  = importlib.import_module('emex.monitors')

    for instance, name, ispkg in pkgutil.walk_packages(emex_monitors_mod.__path__):
        monitor_path = '.'.join(['emex.monitors', monitor_name])

        monitor_mod = importlib.import_module(monitor_path)

        for entry in monitor_mod.__dict__:
            if monitor_name.upper() == entry.upper():
                monitor_class = monitor_mod.__dict__[entry]

                if callable(monitor_class):
                    return monitor_class

    return None


def sock_send_string(sock, in_string):
    format_str = '!I%ds' % len(in_string)

    bufstr = struct.pack(format_str, len(in_string), in_string)

    sock.send(bufstr)


def sock_recv_string(sock):
    (count,) = struct.unpack('!I', sock.recv(4))

    return struct.unpack('%ds' % count, sock.recv(count, socket.MSG_WAITALL))[0]


def get_emex_data_resource_file_path(resource):
    paths = filter(os.path.isfile,
                   [os.path.join(path, resource)
                    for path in emex.data.__path__])

    return list(paths)[0]


def get_emex_data_resource_paths(resource):
    return list(
        filter(os.path.exists,
               [os.path.join(path, resource) for path in emex.data.__path__]))
