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

import re
import logging


class ConfigHelper:
    """
    Interface for configuration helpers. These classes are intended to
    provide a mechanism for implementing and checking configuration
    rules required for emulations to work properly. The idea is to
    programmatically capture the various configuration requirements
    that are tedious to perform by hand. Helper classes inherit this
    interface and are placed in the emex.helper module.
    """
    def configure(self, platforms):
        """
        Configure the platforms according to the rule implemented
        by this class.
        """
        raise NotImplementedError('ConfigHelper.configure')


    def check(self, platforms):
        """
        Check the rule implemented by this class. raise ValueError
        if the rule is not followed.
        """
        raise NotImplementedError('ConfigHelper.check')


    def get_meta_params(self, emoe_rt):
        """
        Returns a set of parameters that can be set or derived from
        the platforms and runtime configuration.
        """
        raise NotImplementedError('ConfigHelper.get_meta_params')


    def get_components(self, platforms, emex_types, value_pattern):
        components = []

        search_types = []

        if isinstance(emex_types, list):
            search_types = emex_types
        else:
            search_types.append(emex_types)

        for plt in platforms:
            for c in plt.components:
                if c.emex_type in search_types and \
                   re.match(value_pattern, c.emex_type_value):
                    components.append((plt.name, c))

        return sorted(components)


    def assign_unique_param_id(self, components, pg_name, p_name, id_pool=range(1,1025)):
        """
        Configure a unique value to the pg_name.p_name of the passed in components.
        Values are selected from the id_pool set.
        """
        assigned = set([])

        unconfigured = []

        # Collect value already assigned and unconfigured components
        for plt_name,c in components:
            param = c.get_param(pg_name, p_name)

            if param and param.value:
                for value in param.value:
                    if value in assigned:
                        raise ValueError(f'"{pg_name}.{p_name}" value {value} '
                                         f'assigned more than once.')

                    assigned.add(value)
            else:
                unconfigured.append(c)

        pool_index = 0

        # assign values to unconfigured components
        for c in unconfigured:
            while id_pool[pool_index] in assigned:
                pool_index += 1

            next_id = id_pool[pool_index]

            c.set_param(pg_name, p_name, next_id)

            assigned.add(next_id)


    def assign_unique_meta_param_id(self, meta_params, components, pg_name, p_name, id_pool=range(1,1025)):
        """
        Configure unique unique value to the pg_name.p_name as a meta param
        for the passed in components. Values are selected from the id_pool set.
        """
        # Collect value already assigned and unconfigured components
        for pool_index,(plt_name,c) in enumerate(components):
            logging.debug(f'{plt_name}.{c.name}.{pg_name}.{p_name}={id_pool[pool_index]}')

            meta_params[(plt_name, c.name)][f'{pg_name}.{p_name}'] = id_pool[pool_index]
