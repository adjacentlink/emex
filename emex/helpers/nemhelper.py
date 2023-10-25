# Copyright (c) 2022 - Adjacent Link LLC, Bridgewater, New Jersey
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


class NemHelper(ConfigHelper):
    """
    NemHelper assigns a unique nemid to all NEMs that
    are not currently assigned one.

    It then checks that all NEMs are assigned a unique
    nemid and raises an exception.
    """
    def configure(self, platforms):
        assigned_nemids = []

        for platform in platforms:
            for c, pg, p, v in platform.get_params():
                if v and p == 'nemid':
                    assigned_nemids.append(v[0])

        assigned_nemids = sorted(set(assigned_nemids))

        next_nemid = 1

        while next_nemid in assigned_nemids:
            next_nemid += 1

        for platform in platforms:
            for c, pg, p, v in platform.get_params():
                if v:
                    continue

                if p == 'nemid':
                    platform.set_param(c, pg, p, next_nemid)

                    assigned_nemids.append(next_nemid)

                    while next_nemid in assigned_nemids:
                        next_nemid += 1


    def check(self, platforms):
        nemids = defaultdict(lambda: [])

        for plt in platforms:
            for c, pg, p, v in plt.get_params():
                if p == 'nemid':
                    if v:
                        nemids[v[0]].append(f'{plt.name}.{c}')

        for nemid, plt_cmps in nemids.items():
            if len(plt_cmps) > 1:
                dups = ', '.join(plt_cmps)

                raise ValueError(f'Error: Duplicate nemid "{nemid}" assigned to {dups}')
