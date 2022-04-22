# -*- coding: utf-8 -*-
#!/usr/bin/env python
#
# LIBTBX_SET_DISPATCHER_NAME cctbx.xfel.trumpet_plots
#
from __future__ import absolute_import, division, print_function
from dials.util import show_mail_on_error
from matplotlib import pyplot as plt
from libtbx.phil import parse
from six.moves import zip

help_message = '''

Make trumpet plots from dials output, one per experiment

See Sauter 2014 (https://doi.org/10.1107/S1399004714024134)

Example:

  cctbx.xfel.trumpet_plots experiment.expt reflections.refl
'''

# Create the phil parameters
phil_scope = parse('''
''', process_includes=True)

from xfel.command_line.detector_residuals import setup_stats, trumpet_plot

class Script(object):
  ''' Class to parse the command line options. '''

  def __init__(self):
    ''' Set the expected options. '''
    from dials.util.options import OptionParser
    import libtbx.load_env

    # Create the option parser
    usage = "usage: %s [options] /path/to/refined/json/file" % libtbx.env.dispatcher_name
    self.parser = OptionParser(
      usage=usage,
      sort_options=True,
      phil=phil_scope,
      read_experiments=True,
      read_reflections=True,
      check_format=False,
      epilog=help_message)

  def run(self):
    ''' Parse the options. '''
    # Parse the command line arguments
    params, options = self.parser.parse_args(show_diff_phil=True)
    self.params = params

    for ewrap, rwrap in zip(params.input.experiments, params.input.reflections):
      experiments = ewrap.data
      reflections = rwrap.data
      reflections = setup_stats(experiments, reflections)
      for expt_id, expt in enumerate(experiments):
        refls = reflections.select(reflections['id'] == expt_id)
        if len(refls) == 0: continue
        trumpet_plot(expt, refls)
    plt.show()

if __name__ == '__main__':
  with show_mail_on_error():
    script = Script()
    script.run()
