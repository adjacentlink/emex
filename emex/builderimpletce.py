# Copyright (c) 2022,2023 - Adjacent Link LLC, Bridgewater, New Jersey
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of Adjacent Link LLC nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
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

import copy
from collections import defaultdict
import logging
from lxml import etree
import os
import pprint
import re
from xml import etree

from yaml import safe_load

from emex.antennabuilder import AntennaBuilder
from emex.containerruntime import ContainerRuntime,BridgeDevice
from emex.eelformatter import EelFormatter
from emex.templateutils import format_file,paramdict_to_namedtuple,TemplateError
from emex.types import platformtypes,antennatypes,waveformtypes,gettype
import emex.utils as utils
import emex.emexd_pb2 as emexd_pb2


class BuilderImplEtce:
    def __init__(self):
        self._platformtypes = platformtypes()

        self._waveformtypes = waveformtypes()

        self._antennatypes = antennatypes()


    @property
    def waveformtypes(self):
        return copy.deepcopy(self._waveformtypes)


    @property
    def antennatypes(self):
        return copy.deepcopy(self._antennatypes)


    @property
    def platformtypes(self):
        return copy.deepcopy(self._platformtypes)


    def build_config(self, emoe_rt, emexd_config):
        os.makedirs(emoe_rt.workdir, mode=0o755)

        configdir = os.path.join(emoe_rt.workdir, 'config')
        os.makedirs(configdir, mode=0o755)

        helperdir = os.path.join(configdir, 'helper-lxc')
        os.makedirs(helperdir, mode=0o755)

        localhostdir = os.path.join(configdir, 'localhost')
        os.makedirs(localhostdir, mode=0o755)

        docdir = os.path.join(configdir, 'doc')
        os.makedirs(docdir, mode=0o755)

        datadir = os.path.join(emoe_rt.workdir, 'data')
        os.makedirs(datadir, mode=0o755)

        lxcdir = os.path.join(emoe_rt.workdir, 'lxcroot')
        os.makedirs(lxcdir, mode=0o755)

        # write test.xml
        self._write_test_file(emoe_rt, configdir)

        # write etce hostfile
        self._write_host_file(emoe_rt, docdir)

        # write lxcconfiguration
        self._write_container_conf(emoe_rt, docdir)

        # write mgen port info
        self._write_mgen_port_map(emoe_rt, docdir)

        # write configuration directory for each platform component
        self._write_platform_configs(emoe_rt, configdir, datadir)

        # write antenna manifest file
        built_antennas = self._write_antenna_files(emoe_rt, configdir)

        # write nemid profileid map
        self._write_nemid_profileid_map(emoe_rt, docdir, built_antennas)

        # steps.xml
        self._write_steps_file(configdir)

        # write EEL file with initial conditions
        self._write_emanephyinit_eel(emoe_rt, helperdir, built_antennas)

        # write opentestpoint broker file
        self._write_testpointbroker_conf(emoe_rt, helperdir)

        # write emane node view file
        self._write_node_view_conf(emoe_rt, localhostdir)

        # write emex tag map file
        self._write_emex_tag_map(emoe_rt, localhostdir)

        # write socat file
        self._write_socat_mappings(emoe_rt, localhostdir)

        # convey config information that needs to pass through to the container
        self._write_emexd_config(docdir, emexd_config)


    def _get_template_path(self, emex_type, value):
        if emex_type == 'waveform' or emex_type == 'host':
            ret = utils.get_emex_data_resource_paths(f'templates/components/{value}')[0]

            return ret
        else:
            return None


    def _write_test_file(self, emoe_rt, configdir):
        test_elem = etree.Element('test')

        name_elem = etree.SubElement(test_elem, 'name')

        name_elem.text = emoe_rt.emoe.name

        description_elem = etree.SubElement(test_elem, 'description')

        text_lines = ['\t\n'] + [ f'\t{plt.name}\n' for plt in emoe_rt.emoe.platforms ]

        description_elem.text = ''.join(text_lines)

        test_elem_tree = test_elem.getroottree()

        test_file = os.path.join(configdir, 'test.xml')

        test_elem_tree.write(test_file, pretty_print=True)


    def _write_platform_configs(self,
                                emoe_rt,
                                configdir,
                                datadir):
        platform_helpers = utils.load_platform_helpers(emoe_rt.emoe.platforms)

        meta_params = defaultdict(lambda: {})

        # combine helper meta params
        for helper in platform_helpers:
            for plt_cmp,helper_params in helper().get_meta_params(emoe_rt).items():
                meta_params[plt_cmp].update(helper_params)

        for (plt_name,c_name),crt in emoe_rt.container_runtimes.items():
            ota_device = crt.get_device('ota0')

            if ota_device:
                logging.debug(f'{plt_name}.{c_name} add ota device{ota_device.ipv4address}')

                meta_params[(plt_name,c_name)].update(
                    {'emex.ota_ipv4address': ota_device.ipv4address})

            control_device = crt.get_device('backchan0')

            if control_device:
                logging.debug(f'{plt_name}.{c_name} add control device{control_device.ipv4address}')

                meta_params[(plt_name,c_name)].update(
                    {'emex.control_ipv4address': control_device.ipv4address})

        # sort platforms lexically by name so that the same emoe
        # will deterministically generate the same configuration.
        for plt in sorted(emoe_rt.emoe.platforms):
            for c in plt.components:
                c_params = { f'{p[1]}.{p[2]}':p[3] for p in c.get_params()
                             if p[0] == c.name }

                hostname = f'{plt.name}-{c.name}'

                fulloutdir = os.path.join(configdir, hostname)

                etype = gettype(c.emex_type, c.emex_type_value)

                templatedir = self._get_template_path(c.emex_type, etype.template)
                built_in_params = {
                    'emex.hostname': [hostname],
                    'emex.log_path': ['${etce_log_path}']
                }

                # add the component param overlays
                built_in_params.update(c_params)

                # and also the meta params from the helper
                built_in_params.update(meta_params[(plt.name,c.name)])

                logging.info(f'building {hostname} config from {templatedir} to {fulloutdir}')

                os.makedirs(fulloutdir, mode=0o755)

                crt = emoe_rt.container_runtimes.get((plt.name,c.name), None)

                # Create an mgenremote.flag file in every traffic endpoint container
                # to trigger execution of an mgen remote instance.
                if crt and crt.traffic_endpoint:
                    open(os.path.join(fulloutdir, 'mgenremote.flag'), 'w').close()
                    open(os.path.join(fulloutdir, 'mgenmonitor.flag'), 'w').close()

                for dirname,_,filenames in os.walk(templatedir):
                    for filename in filenames:
                        srcfile = os.path.join(dirname, filename)

                        dstfile = os.path.join(fulloutdir, filename)
                        try:
                            format_file(srcfile,
                                        dstfile,
                                        paramdict_to_namedtuple(built_in_params))

                        except TemplateError as te:
                            logging.error(f'{te}')


    def _write_antenna_files(self, emoe_rt, configdir):
        builder = AntennaBuilder()

        built_antennas = []

        manifest_elem = etree.Element('profiles')

        for (plt_name,c_name),antennaprofile in emoe_rt.emoe.antenna_assignments.items():
            if antennaprofile in built_antennas:
                continue

            profilefile = builder.build(antennaprofile, configdir)

            built_antennas.append(antennaprofile)

            antennaid = built_antennas.index(antennaprofile) + 1

            profile_elem = etree.SubElement(manifest_elem, 'profile')

            profile_elem.set('id', str(antennaid))

            profile_elem.set('antennapatternuri', os.path.join('/tmp/etce/current_test', profilefile))

            placement_elem = etree.SubElement(profile_elem, 'placement')
            placement_elem.set('north', str(antennaprofile.north))
            placement_elem.set('east', str(antennaprofile.east))
            placement_elem.set('up', str(antennaprofile.up))

        # write the manifest file, this includes case where there are no
        # profiles
        manifest_elem_tree = manifest_elem.getroottree()

        manifest_elem_tree.docinfo.system_url = \
            'file:///usr/share/emane/dtd/antennaprofile.dtd'

        manifest_file = os.path.join(configdir, 'antennaprofilemanifest.xml')

        manifest_elem_tree.write(manifest_file, pretty_print=True)

        return built_antennas


    def _write_host_file(self, emoe_rt, docdir):
        host_file = os.path.join(docdir, 'hostfile')

        with open(host_file, 'w') as hfd:
            hfd.write('localhost {\n')
            hfd.write('localhost\n')
            hfd.write('helper-lxc\n')

            for plt in emoe_rt.emoe.platforms:
                for c in plt.components:
                    hostname = f'{plt.name}-{c.name}'
                    hfd.write('%s\n' % hostname)

            hfd.write('}\n')


    def _write_lxc_conf_block(self, container_elem, container_rt, hostname, counter, subnetid, hostid):
        # lxc.net.0.type=veth
        # lxc.net.0.flags=up
        # lxc.net.0.hwaddr=${interface.hwaddr}
        # lxc.net.0.ipv4.address=${interface.ipv4address}
        # lxc.net.0.name=${interface.device}
        # lxc.net.0.veth.pair=${interface.veth}

        container_elem.set('template', 'basenode')
        container_elem.set('lxc_name', hostname)
        container_elem.set('lxc_indices', str(counter))

        interfaces_elem = etree.SubElement(container_elem, 'interfaces')

        backchan_elem = \
            etree.SubElement(interfaces_elem, 'interface')

        backchan_elem.set('bridge', 'backchan0')

        backchan_elem.set('hosts_entry_ipv4', hostname)

        hwaddr = '02:00:00:00:%02x:%02x' % (subnetid, hostid)
        masklen = 16
        ipv4address = f'10.76.{subnetid}.{hostid}'
        device_name = 'backchan0'

        p = etree.SubElement(backchan_elem, 'parameter')
        p.set('name', 'lxc.net.0.type')
        p.set('value', 'veth')
        p = etree.SubElement(backchan_elem, 'parameter')
        p.set('name', 'lxc.net.0.flags')
        p.set('value', 'up')
        p = etree.SubElement(backchan_elem, 'parameter')
        p.set('name', 'lxc.net.0.hwaddr')
        p.set('value', hwaddr)
        p = etree.SubElement(backchan_elem, 'parameter')
        p.set('name', 'lxc.net.0.ipv4.address')
        p.set('value', f'{ipv4address}/{masklen}')
        p = etree.SubElement(backchan_elem, 'parameter')
        p.set('name', 'lxc.net.0.name')
        p.set('value', device_name)
        p = etree.SubElement(backchan_elem, 'parameter')
        p.set('name', 'lxc.net.0.veth.pair')
        p.set('value', f'veth.ctl.{counter}')
        p = etree.SubElement(backchan_elem, 'parameter')
        p.set('name', 'lxc.net.0.link')
        p.set('value', device_name)

        container_rt.add_device(
            device_name,
            BridgeDevice(
                device_name,
                ipv4address,
                masklen,
                hwaddr))

        ota_elem = \
            etree.SubElement(interfaces_elem, 'interface')

        ota_elem.set('bridge', 'ota0')

        hwaddr = '02:01:00:00:00:%02x' % hostid
        masklen = 16
        ipv4address = f'10.77.{subnetid}.{hostid}'
        device_name = 'ota0'

        p = etree.SubElement(ota_elem, 'parameter')
        p.set('name', 'lxc.net.1.type')
        p.set('value', 'veth')
        p = etree.SubElement(ota_elem, 'parameter')
        p.set('name', 'lxc.net.1.flags')
        p.set('value', 'up')
        p = etree.SubElement(ota_elem, 'parameter')
        p.set('name', 'lxc.net.1.hwaddr')
        p.set('value', hwaddr)
        p = etree.SubElement(ota_elem, 'parameter')
        p.set('name', 'lxc.net.1.ipv4.address')
        p.set('value', f'{ipv4address}/{masklen}')
        p = etree.SubElement(ota_elem, 'parameter')
        p.set('name', 'lxc.net.1.name')
        p.set('value', device_name)
        p = etree.SubElement(ota_elem, 'parameter')
        p.set('name', 'lxc.net.1.veth.pair')
        p.set('value', f'veth.ota.{counter}')
        p = etree.SubElement(ota_elem, 'parameter')
        p.set('name', 'lxc.net.1.link')
        p.set('value', device_name)

        container_rt.add_device(
            device_name,
            BridgeDevice(
                device_name,
                ipv4address,
                masklen,
                hwaddr))


    def _write_container_conf(self, emoe_rt, docdir):
        initsh = utils.get_emex_data_resource_file_path(f'builders/etce/init.sh')

        lxc_conf = utils.get_emex_data_resource_file_path(f'builders/etce/lxc.container.conf')

        net_groups = utils.group_components_by_label(emoe_rt.emoe.platforms, 'net')

        lxcplan_file = os.path.join(docdir, 'lxcplan.xml')

        lxcplan_elem = etree.Element('lxcplan')

        # container templates
        cts_elem = etree.SubElement(lxcplan_elem, 'containertemplates')

        ct_elem = etree.SubElement(cts_elem, 'containertemplate')

        ct_elem.set('name', 'basenode')

        params_elem = etree.SubElement(ct_elem, 'parameters')

        for line in open(lxc_conf, 'r').readlines():
            toks = line.strip().split('=')

            if(len(toks) == 2):
                param_elem = etree.SubElement(params_elem, 'parameter')
                p,v = toks

                param_elem.set('name', p)
                param_elem.set('value', v)

        initscript_elem = etree.SubElement(ct_elem, 'initscript')

        initsh_lines = open(initsh).readlines()

        initscript_elem.text = ''.join(initsh_lines)

        # hosts
        hosts_elem = etree.SubElement(lxcplan_elem, 'hosts')

        host_elem =  etree.SubElement(hosts_elem, 'host')

        host_elem.set('hostname', 'localhost')

        # kernel parameters
        kernelparams_elem = etree.SubElement(host_elem, 'kernelparameters')

        kernelparam_elem = etree.SubElement(kernelparams_elem, 'parameter')

        kernelparam_elem.set('name', 'kernel.sched_rt_runtime_us')
        kernelparam_elem.set('value', '-1')

        # bridges
        bridges_elem = etree.SubElement(host_elem, 'bridges')

        bridge_elem = etree.SubElement(bridges_elem, 'bridge')
        bridge_elem.set('name', 'backchan0')
        ipaddress_elem = etree.SubElement(bridge_elem, 'ipaddress')
        ipv4_elem = etree.SubElement(ipaddress_elem, 'ipv4')
        ipv4_elem.text='10.76.0.250/16'

        bridge_elem = etree.SubElement(bridges_elem, 'bridge')
        bridge_elem.set('name', 'ota0')
        ipaddress_elem = etree.SubElement(bridge_elem, 'ipaddress')
        ipv4_elem = etree.SubElement(ipaddress_elem, 'ipv4')
        ipv4_elem.text='10.77.0.250/16'

        # containers
        containers_elem = etree.SubElement(host_elem, 'containers')

        # Add helper-lxc container
        container_elem = etree.SubElement(containers_elem, 'container')

        counter = 1

        helper_subnetid = 0

        container_rt = emoe_rt.get_container_runtime('helper', 'lxc')

        self._write_lxc_conf_block(container_elem,
                                   container_rt,
                                   'helper-lxc',
                                   counter,
                                   helper_subnetid,
                                   1)  # first host id on helper subnet

        for subnetid,((wft,nl),group_tuples) in enumerate(net_groups.items(), start=helper_subnetid+1):
            for hostid,(platform,component) in enumerate(group_tuples, start=1):
                container_elem = etree.SubElement(containers_elem, 'container')

                counter += 1

                container_rt = emoe_rt.get_container_runtime(platform.name, component.name)

                self._write_lxc_conf_block(container_elem,
                                           container_rt,
                                           f'{platform.name}-{component.name}',
                                           counter,
                                           subnetid,
                                           hostid)

        # write file
        lxcplan_tree = lxcplan_elem.getroottree()

        lxcplan_tree.write(lxcplan_file, pretty_print=True)


    def _write_mgen_port_map(self, emoe_rt, docdir):
        """
         Write out a csvfile with a record for every traffic endpoint
         component

           platformname,hostname,backchan0_ipaddress,mgen_remote_control_port

         The container daemon uses this information to map scenario
         traffic commands (based on platform names), to mgen remote
         control commands sent to the correct destination.
        """
        port_map_file = os.path.join(docdir, 'mgen_port_map.csv')

        with open(port_map_file, 'w') as pmfd:
            for plt_name,crt_hostname,ipv4address,device in emoe_rt.port_map():
                pmfd.write(f'{plt_name},{crt_hostname},{ipv4address},{device}\n')


    def _write_nemid_profileid_map(self, emoe_rt, docdir, built_antennas):
        nemid_map_file = os.path.join(docdir, 'nemid_map.csv')

        antenna_assignments = emoe_rt.emoe.antenna_assignments

        with open(nemid_map_file, 'w') as nifd:
            for (plt_name,c_name),nemid in emoe_rt.nemid_map().items():
                antennaprofile = antenna_assignments.get((plt_name,c_name),None)

                profileid = ''

                if antennaprofile:
                    profileid = built_antennas.index(antennaprofile) + 1

                nifd.write(f'{plt_name},{c_name},{nemid},{profileid}\n')


    def _write_emex_tag_map(self, emoe_rt, localhostdir):
        '''
        <emex-monitor-tag-map>
          <nem>
            <map tag="lteenb-001-r1" nem="1"/>
            <map tag="lteenb-002-r1" nem="2"/>
            <map tag="lteue-001-r1" nem="3"/>
            <map tag="lteue-002-r1" nem="4"/>
          </nem>
          <ip-address>
            <map tag="lteepc-001-h1" ip-address="10.0.1.1"/>
            <map tag="lteue-001-r1" ip-address="10.0.1.2"/>
            <map tag="lteue-002-r1" ip-address="10.0.1.3"/>
          </ip-address>
        </emex-monitor-tag-map>
        '''
        emex_monitor_tag_map = etree.Element('emex-monitor-tag-map')

        nem_elem = etree.SubElement(emex_monitor_tag_map, 'nem')

        for (plt_name,c_name),nemid in emoe_rt.nemid_map().items():
            map_elem = etree.SubElement(nem_elem, 'map')

            map_elem.set('tag', f'{plt_name}-{c_name}')

            map_elem.set('nem', f'{nemid}')

        ip_address_elem = etree.SubElement(emex_monitor_tag_map, 'ip-address')

        for plt_name,crt_hostname,ipv4address,device in emoe_rt.port_map():
            map_elem = etree.SubElement(ip_address_elem, 'map')

            map_elem.set('tag', crt_hostname)

            map_elem.set('ip-address', ipv4address)

        tag_map_tree = emex_monitor_tag_map.getroottree()

        tag_map_file = os.path.join(localhostdir, 'emexjsonserver.xml')

        emoe_rt.add_container_port('emex-jsonserver', 5001)

        tag_map_tree.write(tag_map_file, pretty_print=True)


    def _write_steps_file(self, configdir):
        etce_builders_dirs = utils.get_emex_data_resource_paths(f'builders/etce')

        stepsfiles = []

        for etce_builders_dir in etce_builders_dirs:
            stepsfiles.extend([os.path.join(etce_builders_dir, f)
                               for f in os.listdir(etce_builders_dir)
                               if re.match(r'steps.*\.yml', f)])

        steps_by_order = {}

        for stepfile in stepsfiles:
            steps = safe_load(open(stepfile))

            for step,step_dict in steps.items():
                order = int(step_dict['order'])

                if order in steps_by_order:
                    print('no good')

                steps_by_order[order] = {step: step_dict['wrappers']}

        steps_elem = etree.Element('steps')

        for order,steps in sorted(steps_by_order.items()):
            for step,wrappers in steps.items():
                step_elem = etree.SubElement(steps_elem, 'step')

                step_elem.set('name', step)

                for wrapper,args in wrappers.items():
                    run_elem = etree.SubElement(step_elem, 'run')

                    run_elem.set('wrapper', wrapper)

                    if not args:
                        continue

                    for name,value in args.items():
                        arg_elem = etree.SubElement(run_elem, 'arg')

                        arg_elem.set('name', name)
                        arg_elem.set('value', str(value))

        steps_elem_tree = steps_elem.getroottree()

        steps_xml_file = os.path.join(configdir, 'steps.xml')

        steps_elem_tree.write(steps_xml_file, pretty_print=True)


    def _write_emanephyinit_eel(self, emoe_rt, helperdir, built_antennas):
        formatter = EelFormatter()

        eel_file = os.path.join(helperdir, 'emanephyinit.eel')

        with open(eel_file, 'w+') as efd:
            for ic in emoe_rt.emoe.initial_conditions:
                plt = emoe_rt.emoe.platform_by_name(ic.platform_name)

                if ic.pov:
                    efd.writelines(
                        formatter.pov_to_str('-Inf', plt.nemids, ic.pov))

                if ic.pathlosses:
                    efd.writelines(
                        formatter.pathlosses_to_str('-Inf',
                                                    plt.nemids,
                                                    ic.pathlosses,
                                                    emoe_rt.emoe))

                for ap in ic.antenna_pointings:
                    # The initializer specifies the platform components
                    # that the antenna setting applies to. If no
                    # components are specified, the initializer is
                    # applied to all of the platform components.
                    component_names = list(ap.component_names)
                    if len(component_names) == 0:
                        component_names = plt.component_names

                    for component_name in component_names:
                        nemid = plt.get_param(component_name,
                                              'emane',
                                              'nemid').value[0]

                        antennaprofile = \
                            emoe_rt.emoe.antenna_assignment(ic.platform_name, component_name)

                        if not antennaprofile:
                            logging.warning(f'No profile_id found for component '
                                             f'{ic.platform_name}.{component_name}. Ignoring')

                            continue

                        profile_id = built_antennas.index(antennaprofile) + 1

                        efd.writelines(
                            formatter.antenna_pointing_to_str('-Inf',
                                                              nemid,
                                                              profile_id,
                                                              ap))


    def _write_testpointbroker_conf(self, emoe_rt, helperdir):
        broker_file = os.path.join(helperdir, 'otestpoint-broker.xml')

        broker_elem = etree.Element('otestpoint-broker')

        broker_elem.set('discovery', '0.0.0.0:9001')

        broker_elem.set('publish', '0.0.0.0:9002')

        for (p_name,c_name,_,ipv4address,_,_,cr) in \
            sorted(emoe_rt.control_endpoints()):

            if not cr.testpoint_publisher:
                continue

            hostname = f'{p_name}-{c_name}'

            broker_elem.append(etree.Comment(f'{hostname}'))

            testpoint_elem = etree.SubElement(broker_elem, 'testpoint')

            testpoint_elem.set('discovery', f'{ipv4address}:8881')

            testpoint_elem.set('publish', f'{ipv4address}:8882')
        """
        <otestpoint-broker discovery="0.0.0.0:9001" publish="0.0.0.0:9002">
          <!-- spectrum monitor -->
          <testpoint discovery="10.76.10.1:8881" publish="10.76.10.1:8882"/>

          <!-- lteues -->
          <testpoint discovery="10.76.5.1:8881" publish="10.76.5.1:8882"/>
          <testpoint discovery="10.76.5.2:8881" publish="10.76.5.2:8882"/>
          <testpoint discovery="10.76.5.3:8881" publish="10.76.5.3:8882"/>

          <!-- lteenb -->
          <testpoint discovery="10.76.5.81:8881" publish="10.76.5.81:8882"/>

          <!-- lteepc -->
          <testpoint discovery="10.76.5.91:8881" publish="10.76.5.91:8882"/>

        </otestpoint-broker>
        """
        # write file
        broker_tree = broker_elem.getroottree()

        broker_tree.write(broker_file, pretty_print=True)


    def _write_node_view_conf(self, emoe_rt, localhostdir):
        node_view_file = os.path.join(localhostdir, 'emane-node-view-publisher.xml')

        node_view_elem = etree.Element('emane-node-view-publisher')

        node_view_elem.set('endpoint', 'helper-lxc:9002')

        nodes_elem = etree.SubElement(node_view_elem, 'nodes')

        # keep track of platforms that already have a marker - we only
        # need one marker per platform
        marked_platforms = {}
        proxy_platform = None

        # for each mappable platform, find one contained nemid for
        # publishing location, use it's hostname to indicate
        # the testpoint tag that will be used to show position
        # and use the platform name as the label.

        # proxy everything through one emane node
        """
        <emane-node-view-publisher endpoint="helper-lxc:9002">
          <nodes>
            <node nem-id="501"
                  color="#459e3c"
                  label="lteue-001"
                  tag="lteue-001-r1">
              <proxy>
                <node nem-id="502"
                      color="#459e3c"
                      label="lteue-002/>
                <node nem-id="503"
                      color="#459e3c"
                      label="lteue-003"/>
                <node nem-id="581"
                      color="#FF6600"
                      label="lteenb-001"/>
                <node nem-id="${monitor_nemid}"
                      color="#000000"
                      label="sensor-001"/>
              </proxy>
            </node>
          </nodes>
        </emane-node-view-publisher>
        """
        for (plt_name,c_name),nemid in emoe_rt.nemid_map().items():
            # Only use the location of one component per platform to
            # map the platform position
            if plt_name in marked_platforms:
                continue

            hostname = f'{plt_name}-{c_name}'

            marked_platforms[plt_name] = (nemid, hostname)

            # we need at least one actual emane node that can
            # emit the EMANE.PhysicalLayer.Tables.Events to
            # provide location information to emane-node-view
            if emoe_rt.get_container_runtime(plt_name, c_name).emane_node:
                proxy_platform = plt_name

        if not proxy_platform:
            logging.error('Cannot map platforms, no emane node')
            return

        node_elem = etree.SubElement(nodes_elem, 'node')

        proxy_nemid,proxy_hostname = marked_platforms.pop(proxy_platform)

        node_elem.set('nem-id', str(proxy_nemid))
        node_elem.set('color', '#459e3c')
        node_elem.set('label', proxy_platform)
        node_elem.set('tag', proxy_hostname)

        proxy_elem = etree.SubElement(node_elem, 'proxy')

        for plt_name,(nemid, hostname) in marked_platforms.items():
            node_elem = etree.SubElement(proxy_elem, 'node')

            node_elem.set('nem-id', str(nemid))
            node_elem.set('color', '#459e3c')
            # the label is just the platform name
            node_elem.set('label', plt_name)

        # write file
        node_view_tree = node_view_elem.getroottree()

        # add the access port
        emoe_rt.add_container_port('emane-node-view', 5000)

        node_view_tree.write(node_view_file, pretty_print=True)


    def _write_socat_mappings(self, emoe_rt, localhostdir):
        # map ports this way
        #   3000: emexcontainerd scenario udp port (does not need to be mapped)
        #
        #   3001:           first nem control port
        #   3000 + numnems: last nem control port
        #
        #   5000: emane-node-view
        #   5001: emex-jsonserver
        #   5002: otestpoint-discovery
        #   5003: otestpoint-broker publish
        #
        #   45703: raw emane events multicast
        """
        # container controlport
        TCP-LISTEN:3001,fork,reuseaddr TCP:lteue-001:47000
        TCP-LISTEN:3002,fork,reuseaddr TCP:lteue-002:47000
        TCP-LISTEN:3003,fork,reuseaddr TCP:lteenb-001:47000
        TCP-LISTEN:3004,fork,reuseaddr TCP:lteepc-001:47000

        # sensors
        TCP-LISTEN:4001,fork,reuseaddr TCP:helper-lxc:8801

        # testpoint broker
        TCP-LISTEN:5002,fork,reuseaddr TCP:helper-lxc:9001
        TCP-LISTEN:5003,fork,reuseaddr TCP:helper-lxc:9002

        # emane event service - leave this for now and for documenation, raw eventservice access
        UDP-RECVFROM:45703,reuseaddr,ip-add-membership=224.1.3.1:172.17.0.2,ip-pktinfo,fork UDP4-DATAGRAM:224.1.2.8:45703,range=172.17.0.2/24,ip-multicast-ttl=8,ip-multicast-if=10.76.0.250
        """
        emoe_rt.add_container_port('emexcontainerd', '3000')

        socatfile = os.path.join(localhostdir, 'socat.script')

        port = 3000

        control_ports = {}

        with open(socatfile, 'w+') as sfd:
            sfd.write('# container controlport endpoints\n')

            for i,ep_tpl in enumerate(emoe_rt.control_endpoints(), start=1):
                plt_name,c_name,_,_,_,_,cr = ep_tpl

                emoe_rt.add_container_port('emexcontainerd', '3000')

                if not cr.emane_node:
                    continue

                hostname = f'{plt_name}-{c_name}'

                sfd.write(f'TCP-LISTEN:{port+i},fork,reuseaddr TCP:{hostname}:47000\n')

            sfd.write('\n')
            sfd.write('# testpoint broker endpoints\n')
            sfd.write('TCP-LISTEN:5002,fork,reuseaddr TCP:helper-lxc:9001\n')
            sfd.write('TCP-LISTEN:5003,fork,reuseaddr TCP:helper-lxc:9002\n')

            emoe_rt.add_container_port('otestpoint-discovery', 5002)
            emoe_rt.add_container_port('otestpoint-publish', 5003)

            sfd.write('\n')
            sfd.write('# emane event service endpoint')
            sfd.write('UDP-RECVFROM:45703,reuseaddr,' \
                      'ip-add-membership=%s:172.17.0.2,' \
                      'ip-pktinfo,' \
                      'fork UDP4-DATAGRAM:224.1.2.8:45703,' \
                      'range=172.17.0.2/24,' \
                      'ip-multicast-ttl=8,' \
                      'ip-multicast-if=10.76.0.250\n' % \
                      (emoe_rt.mcast_address))

            # expose any spectrum monitor ports
            next_port = 5004
            for platform in emoe_rt.emoe.platforms:
                for component in platform.components:
                    if component.emex_type_value == 'spectrum_monitor':
                        hostname = f'{platform.name}-{component.name}'
                        sfd.write(f'TCP-LISTEN:{next_port},fork,reuseaddr TCP:{hostname}:8801\n')

                        emoe_rt.add_container_port(hostname, next_port)
                        next_port += 1


    def _write_emexd_config(self, docdir, emexd_config):
        emexd_config_file = os.path.join(docdir, 'emexd-config.csv')

        with open(emexd_config_file, 'w') as efd:
            efd.write(f'emexdirectory-action,{emexd_config.emexdirectory_action}\n')
