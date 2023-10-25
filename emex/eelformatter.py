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


class EelFormatter:
    def pov_to_str(self, time, nemids, pov):
        lines = []

        #-Inf nem:NEMID location gps  38.192924,-75.921039,1000
        #-Inf nem:NEMID orientation pitch,roll,yaw
        #-Inf nem:NEMID velocity az,el,mag
        for nemid in nemids:
            lines.append(f'{time} nem:{nemid} location gps '
                         f'{pov.latitude},{pov.longitude},{pov.altitude}\n')
            lines.append(f'{time} nem:{nemid} orientation '
                         f'{pov.pitch},{pov.roll},{pov.yaw}\n')
            lines.append(f'{time} nem:{nemid} velocity '
                         f'{pov.azimuth},{pov.elevation},{pov.speed}\n')

        return lines


    def pathlosses_to_str(self, time, nemids, pathlosses, emoe):
        lines = []

        for nemid in nemids:
            line = f'{time} nem:{nemid} pathloss'
            for pl in pathlosses:
                remote_nemids = emoe.platform_by_name(pl.remote_platform).nemids

                for rnemid in remote_nemids:
                    line += f' nem:{rnemid},{pl.pathloss}'

            lines.append(f'{line}\n')

        return lines


    def antenna_pointing_to_str(self, time, nemid, profile_id, antenna_pointing):
        #-Inf nem:NEMID antennaprofile profileid,az,el
        lines = []

        lines.append(f'{time} nem:{nemid} antennaprofile '
                     f'{profile_id},'
                     f'{antenna_pointing.azimuth},'
                     f'{antenna_pointing.elevation}\n')

        return lines
