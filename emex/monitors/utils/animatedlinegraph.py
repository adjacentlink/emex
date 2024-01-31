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

from collections import deque


class AnimatedLineGraph(object):
    def __init__(self, fig, ax, x0, y0s, num_points, linelabels, cmap, fixed_ymax=False):
        self._fig = fig
        self._ax = ax
        self._cmap = cmap
        self._fixed_ymax = fixed_ymax
        self._ymax = 10

        # initiate
        self._xs = deque([x0])
        self._num_points = num_points
        self._ys = [ deque([y0]) for y0 in y0s ]

        self._linelabels = linelabels
        self._num_lines = len(linelabels)

        self._lines = []
        for i,(linelabel,ys) in enumerate(zip(self._linelabels, self._ys)):
            self._lines.append(self._ax.plot(self._xs,
                                             ys,
                                             label=linelabel,
                                             color=self._cmap(i/self._num_lines)))


    def ax(self):
        return self._ax


    def figure(self):
        return self._fig


    def set_fixed_ymax(self, fixed):
        self._fixed_ymax = fixed


    def init(self):
        lines = []

        for linelist in self._lines:
            lines.extend(linelist)

        return tuple(lines)


    def update(self, xn, yns):
        scroll = False

        # check if new value is within our current range of
        # xs or is new
        if len(self._xs) >= self._num_points:
            scroll = True

            self._xs.popleft()

        self._xs.append(xn)

        self._lines = []

        for i,(linelabel,ys,yn) in enumerate(zip(self._linelabels, self._ys, yns)):
            # place the new y value
            if scroll:
                ys.popleft()

            ys.append(yn)

            if not self._fixed_ymax:
                if max(ys) > self._ymax:
                    self._ymax = max(ys)

                    self._ax.set_ylim(0, self._ymax + 10)

                    self._ax.set_yticks((0, self._ymax + 10))

            self._lines.append(
                self._ax.plot(
                    self._xs,
                    ys,
                    label=linelabel,
                    color=self._cmap(i/self._num_lines)))

        if scroll:
            self._ax.set_xlim(self._xs[0], self._xs[-1])


    def animate(self, i):
        lines = []

        for linelist in self._lines:
            lines.extend(linelist)

        return tuple(lines)
