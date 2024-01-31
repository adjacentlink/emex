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
import logging
import os

from yaml import safe_load

import emex.data.yml
import emex.emexd_pb2 as emexd_pb2
from emex.platformtemplate import PlatformTemplate
from emex.antennatype import AntennaType
from emex.platformtype import PlatformType
from emex.waveformtype import WaveformType


platformtemplates_dict = {}
platformtypes_dict = {}
waveformtypes_dict = {}
antennatypes_dict = {}


def gettype(emextype, name):
    logging.debug(f'get_type {emextype} {name}')

    if emextype == 'antenna':
        return antennatypes_dict.get(name, None)
    elif emextype == 'waveform' or emextype == 'host':
        return waveformtypes_dict.get(name, None)
    elif emextype == 'platform':
        return platformtypes_dict.get(name, None)
    elif emextype == 'platform_template':
        return platformtemplates_dict.get(name, None)

    return None


def platformtemplates():
    if not platformtemplates_dict:
        _load_yml()
    return platformtemplates_dict


def antennatypes():
    if not antennatypes_dict:
        _load_yml()
    return antennatypes_dict


def waveformtypes():
    if not waveformtypes_dict:
        _load_yml()
    return waveformtypes_dict


def platformtypes():
    if not platformtypes_dict:
        _load_yml()
    return platformtypes_dict


def _load_yml():
    emexpath = os.environ.get('EMEXPATH')

    platforms_paths = []

    if emexpath:
        platforms_paths.append(emexpath)
    else:
        platforms_paths.extend(emex.data.yml.__path__)

    # Load all .yml/.yaml files found in the EMEXPATH tree and
    # organize by type
    ymls = defaultdict(lambda: {})

    logging.info(f'search platforms_paths {platforms_paths} for yml definitions')

    for platforms_path in platforms_paths:
        if not os.path.isdir(platforms_path):
            raise RuntimeError(f'Platforms path "{platforms_path}" does not exist or '
                               'is not a directory. Quitting.')
        logging.debug(f'YML platforms_path={platforms_path}')

        for dirname, _, filenames in os.walk(platforms_path):
            yml_files = [os.path.join(dirname, f) for f in filenames
                         if f.split('.')[-1].lower() in ['yml', 'yaml']]

            for yml_file in yml_files:
                yml = safe_load(open(yml_file))

                logging.debug(f'loading yml_file {yml_file}')

                ymls[yml['type']][yml['name']] = yml

    # instantiate antenna type classes
    for name, template_yml in ymls['antenna'].items():
        antennatypes_dict[name] = AntennaType(template_yml)

    # instantiate waveformtypes from templates
    for name, waveform_yml in ymls['waveform'].items():
        waveformtypes_dict[name] = WaveformType(waveform_yml)
    for name, waveform_yml in ymls['host'].items():
        waveformtypes_dict[name] = WaveformType(waveform_yml)

    # instantiate platform template classes
    for name, template_yml in ymls['platform_template'].items():
        platformtemplates_dict[name] = PlatformTemplate(template_yml)

    # instantiate platformtypes from templates
    for name, platform_yml in ymls['platform'].items():
        platform_template_name = platform_yml['from']['template']

        template = platformtemplates_dict[platform_template_name]

        platformtypes_dict[name] = \
            PlatformType(template.build_config(platform_yml, ymls))
