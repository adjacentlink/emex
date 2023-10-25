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
from emex.confighelper import ConfigHelper
import logging


class PhyHelper(ConfigHelper):
    """
    PhyHelper examines pseudo phy antennaX parameter
    to correctly set values of fixedantennagainenable
    and fixedantennagain.
    """
    def configure(self, platforms):
        pass


    def check(self, platforms):
        pass


    def get_meta_params(self, emoe_rt):
        phy_fixed_gain_settings = {}

        platforms = emoe_rt.emoe.platforms

        for platform in platforms:
            for c, pg, p, v in platform.get_params():
                if v and pg == 'phy' and p == 'antenna0':
                    if v[0].lower().startswith('omni'):
                        # omni antenna0 parameter value may optionally
                        # specify a gain as in omni_20.0.
                        gain = 0.0
                        antenna0_toks = v[0].split('_')

                        if len(antenna0_toks) > 1:
                            gain = float(antenna0_toks[1])

                        logging.debug(
                            f'platform {platform.name} has omni antenna with gain {gain}')

                        phy_fixed_gain_settings[(platform.name, c)] = {
                            'phy.fixedantennagainenable': 'true',
                            'phy.fixedantennagain': gain,
                        }
                    else:
                        logging.debug(
                            f'platform {platform.name} has antenna0 {v[0]}')

                        phy_fixed_gain_settings[(platform.name, c)] = {
                            'phy.fixedantennagainenable': 'false',
                            'phy.fixedantennagain': 0.0,
                        }

        return phy_fixed_gain_settings
