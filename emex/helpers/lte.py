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

from collections import defaultdict

from emex.confighelper import ConfigHelper


class LTE(ConfigHelper):
    """
    LTE helper. Enforces:

       * insure there is one EPC and that the ENB
         and EPC connection parameters are properly
         set
       * setpci values to have non-overlapping
         control channels
       * set and insure unique enb ids.
       * set and insure unique ue imsis.
       * generate epc imsi database
    """
    def configure(self, platforms):
        assigned_macids = set([])

        lte_components = self.get_components(platforms,
                                             ['waveform','host'],
                                             'lte.*')

        grouped_components = self._sort_components(lte_components)

        self._check_one_epc_per_group(grouped_components)

        self._configure_enbs(grouped_components)


    def _sort_components(self, lte_components):
        """
        Return epc, enb and ue components organized by their
        unique labels.
        """
        grouped_components = defaultdict(lambda: ([], [], []))

        for plt_name,c in lte_components:
            if c.emex_type_value == 'lte.epc':
                grouped_components[c.labels][0].append((plt_name,c))
            elif c.emex_type_value == 'lte.enb':
                grouped_components[c.labels][1].append((plt_name,c))
            elif c.emex_type_value == 'lte.ue':
                grouped_components[c.labels][2].append((plt_name,c))

        return grouped_components


    def _configure_enbs(self, grouped_components):
        enbs = []

        for _,group_enbs,_ in grouped_components.values():
            enbs.extend(group_enbs)

        pcis = [8*j+i for i in range(3) for j in range(63)]

        self.assign_unique_param_id(enbs, 'rm', 'pci', id_pool=pcis)


    def _configure_ues_meta(self, lte_meta_params, grouped_components):
        """
        Configure ue imsi and return configs. every ue is assigned
        a unique imsi address
        """
        ues = []

        for _,_,group_ues in grouped_components.values():
            ues.extend(group_ues)

        self.assign_unique_meta_param_id(lte_meta_params, ues, 'rm', 'imsi')


    def _configure_enbs_meta(self, lte_meta_params, grouped_components):
        """
        Configure rm.enbid, rm.pci, rm.cellid and rm.epc_control_ipv4address
        for each enb
        """
        enbs = []

        for _,group_enbs,_ in grouped_components.values():
            enbs.extend(group_enbs)

        self.assign_unique_meta_param_id(lte_meta_params, enbs, 'rm', 'enbid')

        self.assign_unique_meta_param_id(lte_meta_params, enbs, 'rm', 'cellid')


    def _check_one_epc_per_group(self, grouped_components):
        for label,(epcs, enbs, ues) in grouped_components.items():
            if not len(epcs) == 1:
                raise ValueError(f'LTE group "{label}" must have exactly 1 EPC.')


    def check(self, platforms):
        lte_components = self.get_components(platforms,
                                             ['waveform','host'],
                                             'lte.*')


    def get_meta_params(self, emoe_rt):
        platforms = emoe_rt.emoe.platforms

        lte_components = self.get_components(platforms,
                                             ['waveform','host'],
                                             'lte.*')

        grouped_components = self._sort_components(lte_components)

        lte_meta_params = defaultdict(lambda:{})

        self._configure_ues_meta(lte_meta_params, grouped_components)

        self._configure_enbs_meta(lte_meta_params, grouped_components)

        ue_entry_str = defaultdict(lambda:'')

        # for each enb component need to set rm.epc_control_ipv4address
        # with the control address of the associated epc
        for group_epcs,group_enbs,group_ues in grouped_components.values():
            epc_plt_name,group_epc = group_epcs[0]

            crt = emoe_rt.get_container_runtime(epc_plt_name, group_epc.name)

            epc_ctl_device = crt.get_device('backchan0')

            for enb_plt_name,enb_component in group_enbs:
                lte_meta_params[(enb_plt_name,enb_component.name)]['rm.epc_control_ipv4address'] = epc_ctl_device.ipv4address

            for ue_plt_name,ue_component in group_ues:
                ueid = f'{ue_plt_name}-{ue_component.name}'
                imsi = lte_meta_params[(ue_plt_name,ue_component.name)]['rm.imsi']
                ipv4address = ue_component.get_param('net', 'ipv4address').value[0]

                if ue_entry_str[(epc_plt_name,group_epc.name)]:
                    ue_entry_str[(epc_plt_name,group_epc.name)] += '|'

                ue_entry_str[(epc_plt_name,group_epc.name)] += f'{ueid}:{imsi}:{ipv4address}'

            if ue_entry_str[(epc_plt_name,group_epc.name)]:
                lte_meta_params[(epc_plt_name,group_epc.name)]['host.ue_entries'] = \
                    ue_entry_str[(epc_plt_name,group_epc.name)]

        return lte_meta_params
