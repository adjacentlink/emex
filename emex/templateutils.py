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

from collections import defaultdict,namedtuple
import logging

from mako.exceptions import SyntaxException
from mako.template import Template
from mako.runtime import Context
import io


class TemplateError(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)


class CaptureContext(Context):
    def __init__(self):
        self._keys = set([])
        super(CaptureContext, self).__init__(io.StringIO())

    def get(self, key, default=None):
        self._keys.update([key])
        return 40.0

    def get_all_keys(self):
        return self._keys


def get_file_overlays(templatefile):
    t = Template(filename=templatefile)

    ctx = CaptureContext()

    t.render_context(ctx)

    return ctx.get_all_keys()


def format_file(srcfile, dstfile, overlays):
    logging.debug(f'templateutils.format_file srcfile={srcfile} '
                  f'dstfile={dstfile}')

    with open(dstfile, 'w') as outf:
        try:
            template = Template(filename=srcfile, strict_undefined=True)

            outf.write(template.render(**overlays))
        except NameError as ne:
            message = '%s for template file "%s". Quitting.' % (str(ne), srcfile)
            raise TemplateError(message)
        except SyntaxException as se:
            raise TemplateError(str(se))


def format_string(template_string, overlays):
    try:
        template = Template(template_string, strict_undefined=True)

        return template.render(**overlays)
    except NameError as ne:
        message = \
            '%s for template string "%s". Available overlays are {%s}. Quitting.' % \
            (ne.message, template_string, ','.join(overlays.keys()))
        raise TemplateError(message)
    except SyntaxException as se:
        message = 'Syntax error while trying to scan template string "%s". Quitting.' % template_string
        raise TemplateError(message)


def paramdict_to_namedtuple(d):
    """Dynamically create a namedtuple from a parameter dict.

    Args:
        d: An Emex parameter dictionary with key: value format
           paramgroup.paramname: valuelist

    Returns:
        A dict of grouped named tuples. The keys of the dict
        are the unique paramgroup name in the input dict.
        The value for each key is a list of namedtuples each of
        type "paramgroup" and with members paramname for each
        "paramname" found in the composite paramgroup.paramname
        input keys. Each member value is the value of the associated
        input key converted to a string. Where the input value list
        has more than one value, the values are joined by a ','.

        For example:

           in_dict = {
              'a.a': [1],
              'a.b': [2],
              'a.c': [3,4],
              'b.a': [5],
              'b.z': [6]
           }

        Will be converted to:

           out_dict {
              'a': a(a='1', b='2', c='3,4'),
              'b': b(a='b', z='6')
           }

        This is useful for filling in mako templates that have template
        template variable with dot notation: {a.b}.
    """
    sn = defaultdict(lambda: [])
    objs = {}

    for k,v in d.items():
        g,n = k.split('.')

        if not isinstance(v, list):
            v = [v]

        sn[g].append((n,v))

    for g,tpls in sn.items():
        ns,vs = zip(*tpls)
        vstrs = [ ','.join(map(str,v)) for v in vs ]
        gtype = namedtuple(g, ns)
        objs[g] = gtype(*vstrs)

    return objs

