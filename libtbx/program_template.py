'''
Standard Program Template for CCTBX Programs

The "program" is the actual task to be performed without any user interfaces.
The user interfaces (command-line and graphical) build the data_manager and
params objects for the program. The "data_manager"" handles all file input
and "params" handles all the program settings. These two objects should have
all relevant information for the program to run.

The required functions break up the calling order into discrete phases

- constructor: minimal set up
- validate: check that the inputs (files and parameters) are valid and consistent
- run: run the actual task
- get_results: return the desired output from the program

The optional functions provide some extra tweaking

- custom_init: called at the end of the constructor, additional initialization
- clean_up: if temporary files are written in the course of running the program,
            this step should remove those files.

Additional functions and class attributes can be defined for doing the actual
task, but the above functions define a consistent interface.

More documentation to come
'''
from __future__ import absolute_import, division, print_function

import libtbx.phil

from libtbx import Auto, citations
from libtbx.utils import multi_out
from libtbx.version import get_version

# =============================================================================
class ProgramTemplate(object):
  # Class variables for customizing program

  # name of the program, this overrides the LIBTBX_DISPATCHER_NAME
  # environment variable
  program_name = None

  # custom version, this overrides the default version from
  # libtbx.version.get_version
  version = None

  # description of the program
  description = '''
Program Description
'''

  # list of keywords for categorizing the program (optional)
  keywords = None

  # list of maintainer(s) (GitHub names) for the program (optional)
  maintainers = None

  # datatypes for program
  # see iotbx/data_manager/<datatype>.py for list of supported datatypes
  # default datatypes are set in iotbx/data_manager/__init__.py (default_datatypes)
  datatypes = None

  # DataManager options
  # customization for how the DataManager processes files
  # available options are set in iotbx/data_manager/__init__.py (data_manager_options)
  data_manager_options = None

  # customization of master PHIL defined by string
  # this is useful for setting different defaults
  data_manager_custom_master_phil_str = None

  # master PHIL string for the program (required)
  master_phil_str = '''
# example
program {
  parameter = None
    .type = bool
}
'''

  # the DataManager scope includes some shared PHIL parameters
  # set this to true if the DataManager scope should be shown by default
  show_data_manager_scope_by_default = False

  # unique citations for the program. list of citation phil extract objects
  # see libtbx/citations.py for the PHIL format.
  citations = None

  # common citations used by the program that exist in libtbx/citations.params
  # list of article_id strings, e.g. ["polder", "elbow"]).
  known_article_ids = []

  # text shown at the end of the command-line program
  epilog = '''
For additional help, you can contact the developers at cctbxbb@phenix-online.org
or https://github.com/cctbx/cctbx_project

'''

  # ---------------------------------------------------------------------------
  # Reserved phil scope for output
  # This will be automatically added to the master_phil_str.
  # You should add your own output phil scope, but these parameters will be
  # automatically added, so no need to redefine.
  # The filename and file_name parameters refer to the same thing.
  # Changing one will change the other. If multiple values are specified,
  # the last one to be processed is kept.
  output_phil_str = '''
output {
  filename = None
    .alias = file_name
    .type = str
    .help = Manually set filename, overrides filename automatically \
            generated by prefix/suffix/serial
  file_name = None
    .alias = filename
    .type = str
    .help = Same as output.filename
  prefix = None
    .type = str
    .help = Prefix string added to automatically generated output filenames
  suffix = None
    .type = str
    .help = Suffix string added to automatically generated output filenames
  serial = 0
    .type = int
    .help = Serial number added to automatically generated output filenames
  serial_format = "%03d"
    .type = str
    .help = Format for serial number
 target_output_format = *None pdb mmcif
   .type = choice
   .help = Desired output format (if possible). Choices are None (\
            try to use input format), pdb, mmcif.  If output model\
             does not fit in pdb format, mmcif will be used. \
             Default is pdb.
   .short_caption = Desired output format

  overwrite = False
    .type = bool
    .help = Overwrite files when set to True
}
'''

  # ---------------------------------------------------------------------------
  # Advanced features

  # PHIL converters (in a list) for additional PHIL types
  phil_converters = list()

  # ---------------------------------------------------------------------------
  # Convenience features
  def _print(self, text):
    '''
    Print function that just replaces print(text, file=self.logger)
    '''
    print(text, file=self.logger)

  def header(self, text):
    self._print("-"*79)
    self._print(text)
    self._print("*"*len(text))

  # ---------------------------------------------------------------------------
  # Function for showing default citation for template
  @staticmethod
  def show_template_citation(text_width=80, logger=None,
                             citation_format='default'):
    assert logger is not None

    print('\nGeneral citation for CCTBX:', file=logger)
    print('-'*text_width, file=logger)
    print('', file=logger)
    citations.show_citation(citations.citations_db['cctbx'], out=logger,
                            format=citation_format)

  # ---------------------------------------------------------------------------
  def __init__(self, data_manager, params, master_phil=None, logger=None):
    '''
    Common constructor for all programs

    This is supposed to be lightweight. Custom initialization, if necessary,
    should be handled by the custom_init function. Developers should not need to
    override this function.

    Parameters
    ----------
    data_manager :
      An instance of the DataManager (libtbx/data_manager.py) class containing
      data structures from file input
    params :
      An instance of PHIL
    logger :
      Standard Python logger (from logging module), optional. A logger will be
      created if it is not provided.

    '''

    self.data_manager = data_manager
    self.master_phil = master_phil
    self.params = params
    self.logger = logger

    if self.logger is None:
      self.logger = multi_out()

    # master_phil should be provided by CCTBXParser or GUI because of
    # potential PHIL extensions
    if self.master_phil is None:
      self.master_phil = libtbx.phil.parse(
        self.master_phil_str, process_includes=True)

    # set DataManager defaults
    if self.data_manager is not None:
      self.data_manager.set_default_output_filename(
        self.get_default_output_filename())
      self.set_target_output_format()
      try:
        self.data_manager.set_overwrite(self.params.output.overwrite)
      except AttributeError:
        pass
      self.data_manager.set_program(self)

    # optional initialization
    self.custom_init()

  # ---------------------------------------------------------------------------
  def custom_init(self):
    '''
    Optional initialization step

    Developers should override this function if additional initialization is
    needed. There should be no arguments because all necessary information
    should be in self.data_manager (file input) and self.params (phil parameters)

    Parameters
    ----------
    None
    '''
    pass

  # ---------------------------------------------------------------------------
  def validate(self):
    '''

    '''
    raise NotImplementedError('The "validate" function is required.')

  # ---------------------------------------------------------------------------
  def run(self):
    '''

    '''
    raise NotImplementedError('The "run" function is required.')

  # ---------------------------------------------------------------------------
  def clean_up(self):
    '''

    '''
    pass

  # ---------------------------------------------------------------------------
  def get_results(self):
    '''

    '''
    return None

  # ---------------------------------------------------------------------------
  def get_results_as_JSON(self):
    '''

    '''
    return None

  # ---------------------------------------------------------------------------
  def get_program_phil(self, diff=False):
    '''
    Function for getting the PHIL extract of the Program

    Parameters
    ----------
    diff: bool
      When set to True, only the differences from the master PHIL are returned

    Returns
    -------
    params: libtbx.phil.scope
    '''
    working_phil = self.master_phil.format(python_object=self.params)
    if diff:
      working_phil = self.master_phil.fetch_diff(working_phil)
    return working_phil

  # ---------------------------------------------------------------------------
  def get_data_phil(self, diff=False):
    '''
    Function for getting the PHIL scope from the DataManager

    Parameters
    ----------
    diff: bool
      When set to True, only the differences from the master PHIL are returned

    Returns
    -------
    params: libtbx.phil.scope
    '''
    if self.data_manager is None:
      return libtbx.phil.parse('')
    working_phil = self.data_manager.export_phil_scope()
    if diff:
      working_phil = self.data_manager.master_phil.fetch_diff(working_phil)
    return working_phil

  # ---------------------------------------------------------------------------
  def get_program_extract(self, diff=False):
    '''
    Function for getting the PHIL extract of the Program

    Parameters
    ----------
    diff: bool
      When set to True, only the differences from the master PHIL are returned

    Returns
    -------
    params: libtbx.phil.scope_extract
    '''
    return self.get_program_phil(diff=diff).extract()

  # ---------------------------------------------------------------------------
  def get_data_extract(self, diff=False):
    '''
    Function for getting the PHIL extract from the DataManager

    Parameters
    ----------
    diff: bool
      When set to True, only the differences from the master PHIL are returned

    Returns
    -------
    params: libtbx.phil.scope_extract
    '''
    return self.get_data_phil(diff=diff).extract()

  # ---------------------------------------------------------------------------
  def get_program_phil_str(self, diff=False):
    '''
    Function for getting the PHIL string of the Program

    Parameters
    ----------
    diff: bool
      When set to True, only the differences from the master PHIL are returned

    Returns
    -------
    params: str
    '''
    return self.get_program_phil(diff=diff).as_str()

  # ---------------------------------------------------------------------------
  def get_data_phil_str(self, diff=False):
    '''
    Function for getting the PHIL string from the DataManager

    Parameters
    ----------
    diff: bool
      When set to True, only the differences from the master PHIL are returned

    Returns
    -------
    params: str
    '''
    return self.get_data_phil(diff=diff).as_str()

  # ---------------------------------------------------------------------------
  def get_full_phil_str(self, diff=False):
    '''
    Function for getting the full PHIL string of the DataManager and Program

    Parameters
    ----------
    diff: bool
      When set to True, only the differences from the master PHIL are returned

    Returns
    -------
    params: str
    '''
    return self.get_data_phil_str(diff=diff) + self.get_program_phil_str(diff=diff)

  # ---------------------------------------------------------------------------
  def set_target_output_format(self):
    """ Try to set the desired output format if not set by user (pdb or mmcif)
    """
    assert self.data_manager is not None
    if not hasattr(self.data_manager,'set_target_output_format'):
      return # No models in this data_manager

    from iotbx.pdb.utils import set_target_output_format_in_params
    if hasattr(self.data_manager, 'get_default_model_name'):
      file_name = self.data_manager.get_default_model_name()
    else:
      file_name = None
    target_output_format = set_target_output_format_in_params(self.params,
      file_name = file_name,
      out = self.logger)
    self.data_manager.set_target_output_format(target_output_format)


  # ---------------------------------------------------------------------------
  def _params_as_dict(self, params = None, base_name_list = None):
    """ Split up a params object into a dict of each individual parameter name
       as key and value as value. Add base name on to attribute name,
       Recursively traverse the params object."""
    if not params: params = self.params
    if not base_name_list: base_name_list = []
    params_dict = {}
    for x in dir(params):
      if x.startswith("__"): continue
      v = getattr(params,x)
      b = base_name_list + [x]
      if isinstance(v,libtbx.phil.scope_extract):
        self._update_params_dict(params_dict,
             self._params_as_dict(v, base_name_list = b))
      elif isinstance(v, libtbx.phil.scope_extract_list):
        for vv in v:
          if hasattr(vv,'__phil_name__'):
            self._update_params_dict(params_dict,
             self._params_as_dict(vv, base_name_list = b))
          else:
            params_dict[".".join(b)] = vv
      else:
        params_dict[".".join(b)] = v
    return params_dict

  def _update_params_dict(self, params_dict, other_params_dict):
    for key in other_params_dict.keys():
      if not key in params_dict:
        params_dict[key] = other_params_dict[key]
      else:
        if not other_params_dict[key]:
          pass
        elif not params_dict[key]:
          params_dict[key] = other_params_dict[key]
        else:
          if not isinstance(params_dict[key], list):
            params_dict[key] = [ params_dict[key]]
          if not isinstance(other_params_dict[key], list):
            other_params_dict[key] = [ other_params_dict[key]]
          params_dict[key] += other_params_dict[key]
    return params_dict
  def _fn_is_assigned(self, fn = None):
    """ Determine if fn is assigned to some parameter"""
    for x in list(self._params_as_dict().values()):
      if fn == x:
        return True
      if isinstance(x, list) and fn in x:
        return True
    else:
      return False


  def get_parameter_value(self, parameter_name, base = None):
    """ Get the full scope and the parameter from a parameter name.
     Then get value of this parameter
     For example:  autobuild.data -> (self.params.autobuild, 'data')
     returns value of self.params.autobuild.data

     parameter: parameter_name:  text parameter name in context of self.params
     parameter: base: base scope path to add before parameter name
     returns: value of self.params.parameter_name
    """

    scope, par = self._get_scope_and_parameter(parameter_name, base = base)
    if not hasattr(scope, par):
      print("The parameter %s does not exist" %(parameter_name),
         file = self.logger)
    return getattr(scope, par)

  def _get_scope_and_parameter(self, parameter_name = None, base = None):
    """ Get the full scope and the parameter from a parameter name.
     For example:  autobuild.data -> (self.params.autobuild, 'data')
    """
    if base is None:
      base = self.params
    assert parameter_name is not None, "Missing parameter name"
    spl = parameter_name.split(".")
    name = spl[-1]
    path = spl[:-1]
    for p in path:
      assert hasattr(base, p), "Missing scope: %s" %(p)
      base = getattr(base, p)
    return base, name

  def assign_if_value_is_unique_and_unassigned(self,
      parameter_name = None,
      possible_values = None):
    """ Method to assign a value to a parameter that has no value so far,
      choosing value from a list of possible values, eliminating all values
      that have been assigned to another parameter already.
      Normally used like this in a Program template:

      self.assign_if_value_is_unique_and_unassigned(
        parameter_name = 'autobuild.data',
        possible_values = self.data_manager.get_miller_array_names())

      Raises Sorry if there are multiple possibilities.

     parameter: parameter_name:  The name of the parameter in the context
                                 of self.params (self.params.autobuild.data is
                                 autobuild.data)
     parameter: possible_values: Possible values of this parameter, usually from
                                 the data_manager

     sets: value of full parameter to a unique value if present
     returns: None
    """
    v = self.get_parameter_value(parameter_name)

    has_value = not (v in ['Auto',Auto, 'None',None])
    if has_value:
      return # nothing to do, already assigned value to this parameter

    possibilities = []
    for p in possible_values:
      if p in ['Auto',Auto, 'None',None]:
        continue  # not relevant
      elif (not self._fn_is_assigned(p)): # not already assigned
        possibilities.append(p)
    if len(possibilities) == 1:
      scope, par = self._get_scope_and_parameter(parameter_name)
      setattr(scope, par, possibilities[0])
    elif len(possibilities) < 1:
      return # No unused possibilities for this parameter
    else:
      from libtbx.utils import Sorry
      raise Sorry("Please set these parameters with keywords: (%s), " %(
        " ".join(possibilities)) + "\nFor example, '%s=%s'" %(
        parameter_name, possibilities[0]))
  # ---------------------------------------------------------------------------

  def get_default_output_filename(self, prefix=Auto, suffix=Auto, serial=Auto,
    filename=Auto):
    '''
    Given the output.prefix, output.suffix, and output.serial PHIL parameters,
    return the default output filename. The filename is constructed as

      {prefix}{suffix}_{serial:03d}

    However, if output.filename (or output.file_name), that value takes
    precedence.

    Parameters
    ----------
    prefix: str
      The prefix for the name, if set to Auto, the value from output.serial
      is used.
    suffix: str
      The suffix for the name, if set to Auto, the value from output.suffix
      is used.
    serial: int
      The serial number for the name, if set to Auto, the value from
      output.serial is used. Leading zeroes will be added so that the
      number uses 3 spaces.
    filename: str
      A name that overrides the automatically generated name. If set to
      Auto, the value from output.filename is used.

    Returns
    -------
    filename: str
      The default output filename without a file extension
    '''

    # set defaults
    output = None
    if hasattr(self.params, 'output'):
      output = self.params.output

    if prefix is Auto:
      prefix = 'cctbx_program'
      if output and getattr(output, 'prefix', None) is not None:
        prefix = output.prefix
    if suffix is Auto:
      suffix = None
      if output and getattr(output, 'suffix', None) is not None:
        suffix = output.suffix
    if serial is Auto:
      serial = None
      if output and getattr(output, 'serial', None) is not None:
        serial = self.params.output.serial
    else:
      if not isinstance(serial, int):
        raise ValueError('The serial argument should be an integer.')

    # create filename
    if filename is Auto:
      # override if necessary
      if output and getattr(output, 'filename', None) is not None:
        filename = output.filename
      else:
        filename = prefix
        if suffix is not None:
          filename += suffix
        if serial is not None:
          filename += '_{serial:03d}'.format(serial=serial)

    return filename

  # ---------------------------------------------------------------------------
  @classmethod
  def get_version(cls):
    '''
    Function for returning the version

    Parameters
    ----------
    None

    Returns
    -------
    version: str
    '''
    # try the class first
    if cls.version is not None:
      return cls.version

    # the default version
    return get_version()

# =============================================================================

import iotbx.phil
output_phil = iotbx.phil.parse(ProgramTemplate.output_phil_str)
