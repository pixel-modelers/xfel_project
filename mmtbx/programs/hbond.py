from __future__ import division, print_function
from libtbx.program_template import ProgramTemplate
import mmtbx.nci.hbond
import mmtbx.nci.skew_kurt_plot
from libtbx.utils import null_out
import os

# =============================================================================

class Program(ProgramTemplate):

  description = '''
phenix.hbond: tool to find H bonds in an atomic model

Usage example:
  phenix.hbond model.pdb
  '''

  datatypes = ['model', 'phil', 'restraint']

  master_phil_str = mmtbx.nci.hbond.master_phil_str

  # ---------------------------------------------------------------------------
  def validate(self):
    print('Validating inputs', file=self.logger)
    self.data_manager.has_models(raise_sorry=True)

  # ---------------------------------------------------------------------------
  def run(self):
    print('Using model: %s' % self.data_manager.get_default_model_name(),
      file=self.logger)
    model = self.data_manager.get_model()
    model.set_log(log = null_out())
    model.process(make_restraints=True)
    self.results = mmtbx.nci.hbond.find(model = model)
    if self.params.hbond.show_hbonds:
      self.results.show(log = self.logger)
    print("-"*79, file=self.logger)
    self.results.show_summary(log = self.logger)
    prefix=self.params.output.prefix
    if not prefix:
      prefix='%s_hbond' % os.path.basename(
          self.data_manager.get_default_model_name()).split('.')[0]
    if self.params.hbond.output_pymol_file:
      self.results.as_pymol(prefix=prefix)
    if self.params.hbond.output_restraint_file:
      self.results.as_restraints(file_name='%s.eff' % prefix)
    #
    if self.params.hbond.output_stats_pdf:
      mmtbx.nci.hbond.stats(model = model, prefix="%s_stats" % prefix)
    if self.params.hbond.output_skew_kurtosis_plot and self.results.get_counts():
      theta1_data = self.results.get_counts().theta_1
      Rha_data = self.results.get_counts().d_HA
      # To use other than 'all' type, nci.hbond.find needs to be called with selected model again,
      # like in stats().
      fn = '%s_skew_kurtosis' % prefix
      if self.params.hbond.plot_colorblind_friendly:
        fn += "_cbf"
      mmtbx.nci.skew_kurt_plot.make_figure(
          file_name=fn,
          theta1_coords=[theta1_data.skew, theta1_data.kurtosis],
          Rha_coords=[Rha_data.skew, Rha_data.kurtosis],
          type='all',
          colorblind_friendly=self.params.hbond.plot_colorblind_friendly)


  # ---------------------------------------------------------------------------
  def get_results(self):
    return self.results

# =============================================================================
# end
