from __future__ import absolute_import, division, print_function

import os
from mmtbx.validation.rotalyze import rotalyze
from libtbx.program_template import ProgramTemplate
from libtbx.utils import Sorry

class Program(ProgramTemplate):
  prog = os.getenv('LIBTBX_DISPATCHER_NAME')
  description="""\
%(prog)s file.pdb [params.eff] [options ...]

Options:

  model=input_file        input PDB file
  outliers_only=False   only print outliers
  json=False            Outputs results as JSON compatible dictionary
  verbose=False         verbose text output

Example:

  %(prog)s model=1ubq.pdb outliers_only=True
""" % locals()

  master_phil_str = """
  include scope mmtbx.validation.molprobity_cmdline_phil_str
  data_version = 8000
    .type = str
    .help = '''Use rotamer distributions from top8000'''
  show_errors = False
    .type = bool
    .help = '''Print out errors'''
  json = False
    .type = bool
    .help = "Prints results as JSON format dictionary"
  wxplot = False
    .type = bool
    .help = Display interactive plots (requires wxPython and Matplotlib)
  use_parent = False
    .type = bool
  """
  datatypes = ['model','phil']
  data_manager_options = ['model_skip_expand_with_mtrix']
  known_article_ids = ['molprobity']

  def get_results_as_JSON(self):
    hierarchy = self.data_manager.get_model().get_hierarchy()
    hierarchy.atoms().reset_i_seq()

    result = rotalyze(
      pdb_hierarchy=hierarchy,
      data_version="8000",#was 'params.data_version', no options currently
      show_errors=self.params.show_errors,
      outliers_only=self.params.outliers_only,
      use_parent=self.params.use_parent,
      out=self.logger,
      quiet=False)
    return result.as_JSON()

  def validate(self):
    self.data_manager.has_models(raise_sorry=True)

  def run(self):
    hierarchy = self.data_manager.get_model().get_hierarchy()

    result = rotalyze(
      pdb_hierarchy=hierarchy,
      data_version="8000",#was 'params.data_version', no options currently
      show_errors=self.params.show_errors,
      outliers_only=self.params.outliers_only,
      use_parent=self.params.use_parent,
      out=self.logger,
      quiet=False)
    if self.params.json:
      print(result.as_JSON(), file=self.logger)
    elif self.params.verbose:
      result.show_old_output(out=self.logger, verbose=True)
    if self.params.wxplot :
      try :
        import wxtbx.app
      except ImportError as e :
        raise Sorry("wxPython not available.")
      else :
        app = wxtbx.app.CCTBXApp(0)
        result.display_wx_plots()
        app.MainLoop()
