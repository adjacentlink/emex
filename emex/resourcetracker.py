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

import logging


class ResourceTracker():
    def __init__(self, resource_name, allowed_set, increasing=True):
        self._resource_name = resource_name

        # the resources currently available for allocation
        self._available = sorted(list(allowed_set))

        if not increasing:
            # allocate from high to low
            self._available.reverse()

        # the currently allocated resources
        self._allocated = set([])

        # resources excluded from consideration for whatever
        # reason the application requires. members of this
        # move only between this set and available - you
        # can't exlude an allocated resource
        self._excluded = set([])


    @property
    def num_available(self):
        return len(self._available)


    @property
    def num_allocated(self):
        return len(self._allocated)


    @property
    def num_excluded(self):
        return len(self._excluded)


    def allocate(self, num_requested):
        resources = []

        if num_requested > self.num_available:
            logging.error(f'requested {self._resource_name} ({num_requested}) '
                          f'exceeds available ({self.num_available}).')

            return resources

        for i in range(num_requested):
            resources.append(self._available.pop(0))

        self._allocated.update(resources)

        logging.info(f'newly allocated {self._resource_name}s: {resources}')

        self._log_available()

        return resources


    def deallocate(self, allocated):
        for resource in allocated:
            if not resource in self._allocated:
                logging.warning(f'Warning, deallocation of {resource} '
                                f'not currently allocated')
            else:
                self._allocated.remove(resource)

                self._available.append(resource)

        logging.info(f'newly deallocated {self._resource_name}s: {allocated}')

        self._log_available()


    def exclude(self, resource):
        if resource in self._excluded:
            return

        if resource in self._available:
            self._available.remove(resource)

            self._excluded.add(resource)

            logging.info(f'excluding {self._resource_name}: '
                         f'{resource} from allocation pool')

            return

        logging.info(f'ignoring request to exclude {self._resource_name}: {resource} '
                     f'which is not currently available')


    def clear_excluded(self):
        # return excluded resources to available. this may, for example,
        # be attempted if there are not enough resources to allocate
        for resource in self._excluded:
            logging.info(f'return {self._resource_name}: '
                         f'{resource} from excluded to available')

            self._available.add(resource)

        self._excluded.clear()


    def _log_available(self):
        if self.num_available > 10:
            logging.info(f'{self.num_available} {self._resource_name}s '
                         f'available in range '
                         f'[{min(self._available)},{max(self._available)}]')
        else:
            logging.info(f'{self._resource_name}s available: {self._available}')
