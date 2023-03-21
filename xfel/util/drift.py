from __future__ import absolute_import, print_function, division
import abc
import functools
import itertools
from collections import OrderedDict, UserList
from json.decoder import JSONDecodeError
import glob
import os
import pickle
import six
import sys
import tempfile
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple, Union

from dials.array_family import flex  # noqa
from dxtbx.model.experiment_list import ExperimentList  # noqa
from libtbx.phil import parse
from libtbx.utils import Sorry

import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import FixedLocator, PercentFormatter
import numpy as np
import pandas as pd


pd.set_option('display.max_rows', 100)
pd.set_option('display.max_columns', 25)
pd.set_option('display.max_colwidth', 20)

message = """
This script collects and visualizes the spatial drift of a detector and unit
cell parameters as a function of experimental progress. It requires
the directory structure to follow the one resulting from data processing
(i.e. ensemble refinement) performed by cctbx.xfel.
Data scraping can take a lot of time, especially for large datasets.
For this reason, scraping results can be saved and loaded from a pickle cache.
End result is a plot with detector origin position and unit cell lengths
(vertical position) as a function of run & chunk number (horizontal position).
Numbers of reflections and experiments contributing to each batch are drawn
as a bar height and width on the top of the plot.
By default, point and bars' colors reflect the data's folders of origin.
Error bars can be also derived from the uncertainty of individual reflections'
position in laboratory reference system.

Example usage 1:
Read common detector origin position and average unit cell parameters for all
expts merged in "batch*" datasets / directories, excluding "batch5":
excluding those :
    libtbx.python `libtbx.find_in_repositories xfel`/util/drift.py
    scrap.input.glob=batch*/ scrap.input.exclude=batch5/

Example usage 2:
Not only read, but also cache "batch*" results in a "name.pkl" pickle:
    libtbx.python `libtbx.find_in_repositories xfel`/util/drift.py
    scrap.input.glob=batch*/ scrap.cache.action=write scrap.cache.glob=name.pkl

Example usage 3:
Read cached "batch*" results from all "*.pkl" files and save the plot:
    libtbx.python `libtbx.find_in_repositories xfel`/util/drift.py
    scrap.cache.action=read scrap.cache.glob=*.pkl plot.save=True

Example usage 4:
Read distribution of detector origin position, detector origin uncertainty,
and unit cell parameters from selected TDER task209 directories:
    libtbx.python `libtbx.find_in_repositories xfel`/util/drift.py
    scrap.input.glob=r0*/039_rg084/task209 input.kind=tder_task_directory
"""


################################ PHIL HANDLING ################################


phil_scope = parse("""
  scrap {
    input {
      glob = None
        .type = str
        .multiple = True
        .help = glob which matches files after TDER to be investigated.
      exclude = None
        .type = str
        .multiple = True
        .help = glob which matches files to exclude from input.glob
      kind = tder_task_directory *merging_directory
        .type = choice
        .help = The type of files located by input.glob
    }
    cache {
      action = *none read write
        .type = choice
        .help = Read drift table instead of generating one, or write one.
      glob = drift_cache.pkl
        .type = str
        .help = Path to cache(s) with pickled scrap results to write/read
    }
    origin = *first average distribution
      .type = choice
      .help = Use origin of first experiment only or average/distribution of all?
    uncertainties = True
      .type = bool
      .help = If True, uncertainties will be estimated using differences \
            between predicted and observed refl positions and cell distribution
    unit_cell = *average distribution
      .type = choice
      .help = Use average unit cell or distribution of all?
    }
  plot {
    color {
      by = chunk *merge run rungroup task trial
        .type = choice
        .help = Variable to color individual points on drift plot by;
    }
    show = True
      .type = bool
      .help = If False, do not display resulting plot interactively
    save = False
      .type = bool
      .help = If True, save resulting drift plot under plot.path
    path = drift_plot.png
      .type = str
      .help = A path, name, and extension of saved plot (e.g.: drift/fig.png)
    height = 8.0
      .type = float
     .help = Height of saved plot in inches
    width = 10.0
      .type = float
      .help = Width of saved plot in inches
  }
""")


def params_from_phil(args):
  user_phil = []
  for arg in args:
    if os.path.isfile(arg):
      user_phil.append(parse(file_name=arg))
    else:
      try:
        user_phil.append(parse(arg))
      except Exception:
        raise Sorry("Unrecognized argument: %s" % arg)
  params_ = phil_scope.fetch(sources=user_phil).extract()
  return params_


DEFAULT_INPUT_SCOPE = parse("""
  input {
    path = None
      .multiple = True
      .type = str
    experiments_suffix = .expt
      .type = str
    reflections_suffix = .refl
      .type = str
    experiments = None
      .multiple = True
      .type = str
    reflections = None
      .multiple = True
      .type = str
}
""")


############################### MATHS FUNCTIONS ###############################


def average(xs: Sequence, weights: Sequence = None) -> float:
  """Calculate weighted arithmetic mean of a sequence"""
  xs = np.array(xs)
  weights = np.ones((len(xs))) if weights is None else np.array(weights)
  return sum(xs * weights) / sum(weights)


def correlation(xs: Sequence, ys: Sequence, weights: Sequence = None) -> float:
  """Calculate weighted Pearson's correlation coefficient between sequences"""
  weights = np.ones((len(xs))) if weights is None else np.array(weights)
  x_variance = variance(xs, xs, weights=weights)
  y_variance = variance(ys, ys, weights=weights)
  covariance = variance(xs, ys, weights=weights)
  return covariance / (x_variance * y_variance) ** 0.5


def variance(xs: Sequence, ys: Sequence, weights: Sequence = None) -> float:
  """Calculate weighted variance between sequences"""
  weights = np.ones((len(xs))) if weights is None else np.array(weights)
  x_average = average(xs, weights=weights)
  y_average = average(ys, weights=weights)
  x_deviations = np.array(xs) - x_average
  y_deviations = np.array(ys) - y_average
  return sum(weights * x_deviations * y_deviations) / sum(weights)


def normalize(sequence: Sequence, floor: float = 0., ceiling: float = 1.) \
        -> Sequence:
  """Normalize `sequence`'s values to lie between `floor` and `ceiling`"""
  min_, max_ = min(sequence), max(sequence)
  old_span = max_ - min_
  new_span = ceiling - floor
  normalized = [new_span * (s - min_) / old_span + floor for s in sequence]
  return sequence if min_ == max_ else normalized


class CorrelationMatrix(object):
  """Calculate, store, and print correlation matrix between many sequences"""

  def __init__(self, variables: Dict[str, Sequence], weights: Sequence = None):
    """Calculate corr. matrix between every pair in `variables` dict-like"""
    self.keys = variables.keys()
    self.corr = {k: {} for k in self.keys}
    for i1, k1 in enumerate(self.keys):
      for i2, k2 in enumerate(self.keys):
        if i1 == i2:
          self.corr[k1][k2] = self.corr[k2][k1] = 1.0
        elif len(variables[k1]) < 2:
          self.corr[k1][k2] = self.corr[k2][k1] = 0.0
        elif i2 > i1:
          try:
            corr = correlation(variables[k1], variables[k2], weights=weights)
          except ZeroDivisionError:
            corr = 0
          self.corr[k1][k2] = self.corr[k2][k1] = corr

  def __str__(self) -> str:
    s = 'Correl. ' + ' '.join('{:>7}'.format(k) for k in self.keys)
    for k1 in self.keys:
      s += '\n{:7}'.format(k1)
      for k2 in self.keys:
        s += ' {:+6.4f}'.format(self.corr[k1][k2])
    return s


############################## UTILITY FUNCTIONS ##############################


def is_iterable(value: object, count_str: bool = False):
  """Return `True` if object is iterable and not string, else `False`"""
  if not count_str and isinstance(value, str):
    return False
  try:
    iter(value)  # noqa
  except TypeError:
    return False
  else:
    return True


def path_join(*path_elements: str) -> str:
  """Join path from elements, resolving all redundant or relative calls"""
  path_elements = [os.pardir if p == '..' else p for p in path_elements]
  return os.path.normpath(os.path.join(*path_elements))


def path_lookup(*path_elements: str) -> List[str]:
  """Join path elements and return a list of all matching files/dirs"""
  return glob.glob(path_join(*path_elements), recursive=True)


def path_split(path: str) -> List[str]:
  """Split path into directories and file basename using os separator"""
  return os.path.normpath(path).split(os.sep)


def read_experiments(*expt_paths: str) -> ExperimentList:
  """Create an instance of ExperimentList from one or more `*expt_paths`"""
  expts = ExperimentList()
  for expt_path in unique_elements(expt_paths):
    expts.extend(ExperimentList.from_file(expt_path, check_format=False))
  return expts


def read_reflections(*refl_paths: str) -> flex.reflection_table:
  """Create an instance of flex.reflection_table from one/more `*refl_paths`"""
  r = [flex.reflection_table.from_file(p) for p in unique_elements(refl_paths)]
  return flex.reflection_table.concat(r)


def represent_range_as_str(sorted_iterable: Sequence) -> str:
  """Return str in only one in iterable, range e.g. "r00[81-94]" otherwise"""
  fs, ls = str(sorted_iterable[0]), str(sorted_iterable[-1])
  d = min([i for i, (fl, ll) in enumerate(zip(fs, ls)) if fl != ll] or [None])
  return fs if not d else fs[:d] + '[' + fs[d:] + '-' + ls[d:] + ']'


def unique_elements(sequence: Sequence) -> List:
  """Return list of unique elements in sequence while preserving its order"""
  return list(OrderedDict.fromkeys(sequence))


############################### DRIFT SCRAPPING ###############################


class ScrapResults(UserList):
  """Responsible for storing and pickling DriftScraper results."""
  def __init__(self, parameters) -> None:
    super().__init__()
    self.parameters = parameters

  def read(self) -> None:
    scrap_paths, scrap_results = [], []
    for scg in path_lookup(self.parameters.scrap.cache.glob):
      scrap_paths.extend(glob.glob(scg))
    for scrap_path in scrap_paths:
      with open(scrap_path, 'rb') as pickle_file:
        self.extend(pickle.load(pickle_file))

  def write(self) -> None:
    write_path = self.parameters.scrap.cache.glob
    with open(write_path, 'wb') as pickle_file:
      pickle.dump(self, pickle_file)


def handle_scrap_cache(scrap: Callable) -> Callable:
  @functools.wraps(scrap)
  def scrap_wrapper(self: 'BaseDriftScraper', *args: Any, **kwargs: Any):
    if self.parameters.scrap.cache.action == 'read':
      self.scrap_results.read()
    scrap(self, *args, **kwargs)
    if self.parameters.scrap.cache.action == 'write':
      self.scrap_results.write()
    for scrap_dict in self.scrap_results:
      self.table.add(scrap_dict)
  return scrap_wrapper


class DriftScraperRegistrar(abc.ABCMeta):
  """Metaclass for `DriftScraper`s, auto-registers them by `input_kind`."""
  REGISTRY = {}
  def __new__(mcs, name, bases, attrs):
    new_cls = super().__new__(mcs, name, bases, attrs)
    if hasattr(new_cls, 'input_kind') and new_cls.input_kind:
      mcs.REGISTRY[new_cls.input_kind] = new_cls
    return new_cls


@six.add_metaclass(DriftScraperRegistrar)
class BaseDriftScraper(object):
  """Base class for scraping cctbx.xfel output into instance of `DriftTable`,
  with automatic registration into the `DriftScraperRegistrar`."""

  def __init__(self, table: 'DriftTable', parameters) -> None:
    self.table = table
    self.parameters = parameters
    self.scrap_results = ScrapResults(parameters)

  @staticmethod
  def calc_expt_refl_len(expts: ExperimentList, refls: flex.reflection_table) \
          -> Tuple[int, flex.int]:
    expts_len = len(expts)
    refls_lens = flex.int()
    for expt_id, expt in enumerate(expts):
      refls_lens.append((expt_id == refls['id']).count(True))
    return expts_len, refls_lens

  @staticmethod
  def extract_db_metadata(combine_phil_path: str) -> dict:
    """Get trial, task, rungroup, chunk, run info based on combining phil"""
    parsed_combine_phil = parse(file_name=combine_phil_path)
    phil = DEFAULT_INPUT_SCOPE.fetch(sources=[parsed_combine_phil]).extract()
    index_dirs = [path_join(pie, '..') for pie in phil.input.experiments]
    rungroups = sorted(set(index_dir[-7:-4] for index_dir in index_dirs))
    trials = sorted(set(index_dir[-13:-10] for index_dir in index_dirs))
    runs = sorted(set(index_dir[-19:-14] for index_dir in index_dirs))
    return {'chunk': int(path_split(combine_phil_path)[-1][16:19]),
            'run': represent_range_as_str(runs),
            'rungroup': represent_range_as_str(rungroups),
            'task': path_split(combine_phil_path)[-4],
            'trial': represent_range_as_str(trials)}

  def locate_input_paths(self) -> List:
    """Return all paths (either common files or directories, relative to
    working directory) of specified kind to be processed"""
    input_paths, exclude_paths = [], []
    for ig in self.parameters.scrap.input.glob:
      input_paths.extend(glob.glob(ig))
    for ie in self.parameters.scrap.input.exclude:
      exclude_paths.extend(glob.glob(ie))
    return [it for it in input_paths if it not in exclude_paths]

  @staticmethod
  def locate_combining_phil_paths(scaling_phil_paths: Iterable[str]) -> List:
    """Return paths to all phil files used to combine later-scaled expts"""
    parsed_scaling_phil = [parse(file_name=spp) for spp in scaling_phil_paths]
    phil = DEFAULT_INPUT_SCOPE.fetch(sources=parsed_scaling_phil).extract()
    combine_dirs = [path_join(ip, '..') for ip in phil.input.path]
    combine_phil_paths = []
    for cd in combine_dirs:
      combine_phil_paths.extend(path_lookup(cd, '*chunk*_combine_*.phil'))
    return sorted(set(combine_phil_paths))

  @staticmethod
  def locate_scaling_directories(merging_phil_paths: Iterable[str]) -> List:
    """Return paths to all directories specified as scrap.input.glob in phil"""
    merging_phils = [parse(file_name=mpp) for mpp in merging_phil_paths]
    phil = DEFAULT_INPUT_SCOPE.fetch(sources=merging_phils).extract()
    return sorted(set(phil.input.path))

  @staticmethod
  def locate_refined_expts_refls(combine_phil_path: str) \
          -> Tuple[ExperimentList, flex.reflection_table]:
    """Return all refined expts and refls down-stream from combine_phil_path"""
    path_stem = combine_phil_path.replace('_combine_experiments.phil', '')
    expts_paths = path_lookup(path_stem + '_refined.expt')
    refls_paths = path_lookup(path_stem + '_refined.refl')
    expts = read_experiments(*expts_paths)
    refls = read_reflections(*refls_paths)
    return expts, refls

  @abc.abstractmethod
  @handle_scrap_cache
  def scrap(self) -> None:
    """Prepare `ScrapResults` list used by `handle_scrap_cache` to create
    `self.table`, instance of `DriftTable`, based on `self.parameters`."""
    pass


class TderTaskDirectoryDriftScraper(BaseDriftScraper):
  """Drift scraper which looks for all TDER downstream from merging"""
  input_kind = 'tder_task_directory'

  @handle_scrap_cache
  def scrap(self) -> None:
    combining_phil_paths = []
    for tder_task_directory in self.locate_input_paths():
      cpp = path_lookup(tder_task_directory, 'combine_experiments_t*',
                        'intermediates', '*chunk*_combine_*.phil')
      combining_phil_paths.extend(cpp)
    for cpp in unique_elements(combining_phil_paths):  # combine.phil paths
      try:
        scrap_dict = {'merge': "None"}
        scrap_dict.update(self.extract_db_metadata(cpp))
        print('Processing run {}'.format(scrap_dict['run']))
        refined_expts, refined_refls = self.locate_refined_expts_refls(cpp)
        elen, rlen = self.calc_expt_refl_len(refined_expts, refined_refls)
        print(f'Found {elen} expts and {sum(rlen)} refls')
        scrap_dict.update({'expts': elen, 'refls': rlen})
        scrap_dict.update(self.get_origin(refined_expts))
        scrap_dict.update(self.get_unit_cell(refined_expts))
        scrap_dict.update(self.get_origin_deltas(refined_expts, refined_refls))
      except (KeyError, IndexError, JSONDecodeError) as e:
        print(e)
      else:
        self.scrap_results.append(scrap_dict)



class MergingDirectoryDriftScraper(BaseDriftScraper):
  """Drift scraper which directly looks for TDER task directories"""
  input_kind = 'merging_directory'

  @handle_scrap_cache
  def scrap(self) -> None:
    for merge in self.locate_input_paths():
      merging_phil_paths = path_lookup(merge, '**', '*.phil')
      merging_phil_paths.sort(key=os.path.getmtime)
      for scaling_dir in self.locate_scaling_directories(merging_phil_paths):
        scaled_expt_paths = path_lookup(scaling_dir, 'scaling_*.expt')
        scaled_expts = read_experiments(*scaled_expt_paths)
        scaled_identifiers = list(scaled_expts.identifiers())
        scaling_phil_paths = []
        for sep in scaled_expt_paths:
          scaling_phil_paths.extend(path_lookup(sep, '..', '..', '*.phil'))
        comb_phil_paths = self.locate_combining_phil_paths(scaling_phil_paths)
        for cpp in unique_elements(comb_phil_paths):
          try:
            scrap_dict = {'merge': merge}
            scrap_dict.update(self.extract_db_metadata(cpp))
            print('Processing run {} in merge {}'.format(scrap_dict['run'], merge))
            refined_expts, refined_refls = self.locate_refined_expts_refls(cpp)
            elen, rlen = self.calc_expt_refl_len(refined_expts, refined_refls)
            print(f'Found {elen} expts and {sum(rlen)} refls')
            refined_expts.select_on_experiment_identifiers(scaled_identifiers)
            refined_refls = refined_refls.select(refined_expts)
            elen, rlen = self.calc_expt_refl_len(refined_expts, refined_refls)
            print(f'Accepted {elen} expts and {sum(rlen)} refls')
            scrap_dict.update({'expts': elen, 'refls': rlen})
            scrap_dict.update(self.get_origin(refined_expts))
            scrap_dict.update(self.get_unit_cell(refined_expts))
            scrap_dict.update(self.get_origin_deltas(refined_expts, refined_refls))
          except (KeyError, IndexError, JSONDecodeError) as e:
            print(e)
          else:
            self.scrap_results.append(scrap_dict)


class FirstOriginMixin(object):
  @staticmethod
  def get_origin(expts: ExperimentList) -> Dict[str, float]:
    """Read detector origin (x, y, z) from the first expt file only"""
    x, y, z = expts[0].detector.hierarchy().get_origin()
    return {'x': x, 'y': y, 'z': z}


class AverageOriginMixin(object):
  @staticmethod
  def get_origin(expts: ExperimentList) -> Dict[str, float]:
    """Read detector origin (x, y, z) from the first expt file"""
    xs, ys, zs = flex.double(), flex.double(), flex.double()
    for expt in expts:
      x, y, z = expt.detector.hierarchy().get_origin()
      xs.append(x)
      ys.append(y)
      zs.append(z)
    return {'x': flex.mean(xs), 'y': flex.mean(ys), 'z': flex.mean(zs)}


class DistributionOriginMixin(object):
  @staticmethod
  def get_origin(expts: ExperimentList) -> Dict[str, flex.double]:
    """Read detector origin (x, y, z) from the first expt file"""
    xs, ys, zs = flex.double(), flex.double(), flex.double()
    for expt in expts:
      x, y, z = expt.detector.hierarchy().get_origin()
      xs.append(x)
      ys.append(y)
      zs.append(z)
    return {'x': xs, 'y': ys, 'z': zs}


class FalseUncertaintiesMixin(object):
  @staticmethod
  def get_origin_deltas(expts: ExperimentList, refls: flex.reflection_table) \
          -> Dict[str, float]:
    """If uncertainties=False, return dummy zero origin uncertainties"""
    return {'delta_x': 0., 'delta_y': 0., 'delta_z': 0.}


class TrueUncertaintiesMixin(object):
  @staticmethod
  def get_origin_deltas(expts: ExperimentList, refls: flex.reflection_table) \
          -> Dict[str, float]:
    """Get uncertainties of origin positions from refl. position deviations"""
    deltas_flex = flex.vec3_double()
    for panel in expts[0].detector:
      pr = refls.select(refls['panel'] == panel.index())      # pr: panel refls
      pr_obs_det = pr['xyzobs.mm.value'].parts()[0:2]  # det: in detector space
      pr_cal_det = pr['xyzcal.mm'].parts()[0:2]        # lab: in labor. space
      pr_obs_lab = panel.get_lab_coord(flex.vec2_double(*pr_obs_det))
      pr_cal_lab = panel.get_lab_coord(flex.vec2_double(*pr_cal_det))
      deltas_flex.extend(pr_obs_lab - pr_cal_lab)
    d = [flex.mean(flex.abs(deltas_flex.parts()[i])) for i in range(3)]
    return {'delta_x': d[0], 'delta_y': d[1], 'delta_z': d[2]}


class BaseUnitCellMixin(object):
  @staticmethod
  def _write_tdata(expts: ExperimentList, tdata_path: str) -> None:
    """Read all expt_paths and write a tdata file with unit cells in lines"""
    s = '{:.4f} {:.4f} {:.4f} {:.4f} {:.4f} {:.4f} {}'
    tdata_lines = []
    for expt in expts:
      uc_params = expt.crystal.get_unit_cell().parameters()
      sg = expt.crystal.get_space_group().type().universal_hermann_mauguin_symbol()
      tdata_lines.append(s.format(*uc_params, sg.replace(' ', '')))
    with open(tdata_path, 'w') as tdata_file:
      tdata_file.write('\n'.join(tdata_lines))


class AverageUnitCellMixin(BaseUnitCellMixin):
  def get_unit_cell(self, expts: ExperimentList) -> Dict[str, float]:
    """Retrieve average a, b, c and their deltas using expt paths"""
    af, bf, cf = flex.double(), flex.double(), flex.double()
    with tempfile.NamedTemporaryFile() as tdata_file:
      self._write_tdata(expts, tdata_file.name)
      with open(tdata_file.name, 'r') as tdata:
        for line in tdata.read().splitlines():
          a, b, c = line.strip().split(' ')[:3]
          af.append(float(a))
          bf.append(float(b))
          cf.append(float(c))
    return {'a': flex.mean(af), 'b': flex.mean(bf), 'c': flex.mean(cf),
            'delta_a': af.standard_deviation_of_the_sample(),
            'delta_b': bf.standard_deviation_of_the_sample(),
            'delta_c': cf.standard_deviation_of_the_sample()}


class DistributionUnitCellMixin(BaseUnitCellMixin):
  def get_unit_cell(self, expts: ExperimentList) \
          -> Dict[str, Union[flex.double, float]]:
    """Retrieve distribution of a, b, c and their deltas using expt paths"""
    af, bf, cf = flex.double(), flex.double(), flex.double()
    with tempfile.NamedTemporaryFile() as tdata_file:
      self._write_tdata(expts, tdata_file.name)
      with open(tdata_file.name, 'r') as tdata:
        for line in tdata.read().splitlines():
          a, b, c = line.strip().split(' ')[:3]
          af.append(float(a))
          bf.append(float(b))
          cf.append(float(c))
    return {'a': af, 'b': bf, 'c': cf,
            'delta_a': af.standard_deviation_of_the_sample(),
            'delta_b': bf.standard_deviation_of_the_sample(),
            'delta_c': cf.standard_deviation_of_the_sample()}


class DriftScraperFactory(object):
  """Produces appropriate DriftScraper class based on phil `parameters`."""
  ORIGIN_MIXINS = {
    'first': FirstOriginMixin,
    'average': AverageOriginMixin,
    'distribution': DistributionOriginMixin,
  }
  UNCERTAINTIES_MIXINS = {
    True: TrueUncertaintiesMixin,
    False: FalseUncertaintiesMixin,
  }
  UNIT_CELL_MIXINS = {
    'average': AverageUnitCellMixin,
    'distribution': DistributionUnitCellMixin,
  }

  @classmethod
  def get_drift_scraper(cls, table: 'DriftTable', parameters) \
          -> BaseDriftScraper:
    base = DriftScraperRegistrar.REGISTRY[parameters.scrap.input.kind]
    mixins = [
      cls.ORIGIN_MIXINS[parameters.scrap.origin],
      cls.UNCERTAINTIES_MIXINS[parameters.scrap.uncertainties],
      cls.UNIT_CELL_MIXINS[parameters.scrap.unit_cell],
    ]
    class DriftScraper(base, *mixins):
      pass
    return DriftScraper(table=table, parameters=parameters)


################################ DRIFT STORAGE ################################


class DriftTable(object):
  """Class responsible for storing all info collected by `DriftScraper`"""
  STATIC_KEYS = ['merge', 'run', 'rungroup', 'trial', 'chunk', 'task',
                 'x', 'y', 'z', 'delta_x', 'delta_y', 'delta_z', 'expts',
                 'refls', 'a', 'b', 'c', 'delta_a', 'delta_b', 'delta_c']
  DYNAMIC_KEYS = ['density']

  def __init__(self):
    self.data = pd.DataFrame()

  def __getitem__(self, key: str) -> pd.Series:
    if key in self.DYNAMIC_KEYS:
      self.recalculate_dynamic_column(key)
    return self.data[key]

  def __len__(self) -> int:
    return len(self.data.index)

  def __str__(self) -> str:
    for key in self.DYNAMIC_KEYS:
      self.recalculate_dynamic_column(key)
    return str(self.data)

  def add(self, d: dict) -> None:
    d_is_bumpy = any(is_iterable(d[k]) for k in d.keys() if k != 'refls')
    d_is_all_flat = all(not is_iterable(d[k]) for k in d.keys())
    if d_is_bumpy or d_is_all_flat:
      d2 = d
    else:  # if only 'refls' column is iterable, immediately sum it
      d2 = {k: sum(v) if k == 'refls' else v for k, v in d.items()}
    pd_kwargs = {'index': [0]} #{} if d_is_bumpy else {'index': [0]}
    new_rows = pd.DataFrame(d2, **pd_kwargs)
    self.data = pd.concat([self.data, new_rows], ignore_index=True)

  def get(self, key: str, default: Any = None) -> pd.Series:
    return self[key] if key in self.data.columns else default

  def sort(self, by: Union[str, Sequence[str]]) -> None:
    self.data.sort_values(by=by, ignore_index=True)

  def column_is_flat(self, key: str) -> bool:
    return not is_iterable(self[key][0])

  @property
  def flat(self) -> pd.DataFrame:
    """Pandas' data `DataFrame` with all iterable fields expanded over rows"""
    c = self.column_is_flat
    col_names = self.data.columns
    flatteners = [itertools.repeat if c(k) else lambda x: x for k in col_names]
    set_all_expt_count_to_1 = False
    flat_sub_tables = []
    for i, row in enumerate(self.data.itertuples(index=False)):
      lens = [len(el) for el in row if is_iterable(el)]
      if len(unique_elements(lens)) > 1:
        raise ValueError('All row elements must be scalars or same-length')
      elif len(unique_elements(lens)) == 1:
        flat_rows = zip(*[f(cell) for cell, f in zip(row, flatteners)])
        flat_columns = [flat_col for flat_col in zip(*flat_rows)]
        set_all_expt_count_to_1 = True
      else:
        flat_columns = [[cell] for cell in row]
      fst = pd.DataFrame({k: v for k, v in zip(col_names, flat_columns)})
      fst['original_index'] = i
      flat_sub_tables.append(fst)
    flat_table = pd.concat(flat_sub_tables, ignore_index=True)
    if set_all_expt_count_to_1:
      flat_table['expts'] = 1
    return flat_table

  def recalculate_dynamic_column(self, key: str) -> None:
    if key == 'density':
      refls = self.data['refls'] if self.column_is_flat('refls') \
        else pd.Series([sum(refl) for refl in self.data['refls']])
      self.data['density'] = refls / self.data['expts']
    else:
      raise KeyError(f'Unknown dynamic column key: {key}')


############################## DRIFT VISUALIZING ##############################


class DriftArtist(object):
  """Object responsible for plotting an instance of `DriftTable`."""
  def __init__(self, table: DriftTable, parameters):
    self.colormap = plt.get_cmap('tab10')
    self.colormap_period = 10
    self.cov_colormap = plt.get_cmap('seismic')
    self.order_by = ['run', 'chunk']
    self.table = table
    self.table_flat: pd.DataFrame
    self.parameters = parameters
    self._init_figure()
    self._setup_figure()

  def _init_figure(self) -> None:
    self.fig = plt.figure(tight_layout=True)
    gs = GridSpec(7, 2, hspace=0, wspace=0, width_ratios=[4, 1],
                  height_ratios=[2, 3, 3, 3, 3, 3, 3])
    self.axh = self.fig.add_subplot(gs[0, 0])
    self.axx = self.fig.add_subplot(gs[1, 0], sharex=self.axh)
    self.axy = self.fig.add_subplot(gs[2, 0], sharex=self.axh)
    self.axz = self.fig.add_subplot(gs[3, 0], sharex=self.axh)
    self.axa = self.fig.add_subplot(gs[4, 0], sharex=self.axh)
    self.axb = self.fig.add_subplot(gs[5, 0], sharex=self.axh)
    self.axc = self.fig.add_subplot(gs[6, 0], sharex=self.axh)
    self.axw = self.fig.add_subplot(gs[0, 1])
    self.axl = self.fig.add_subplot(gs[1:, 1])

  def _setup_figure(self) -> None:
    self.axl.axis('off')
    self.axw.axis('off')
    self.axh.spines['top'].set_visible(False)
    self.axh.spines['right'].set_visible(False)
    self.axh.spines['bottom'].set_visible(False)
    self.axh.set_zorder(self.axx.get_zorder() - 1.0)
    common = {'direction': 'inout', 'top': True, 'bottom': True, 'length': 6}
    main_axes = self.axx, self.axy, self.axz, self.axa, self.axb, self.axc
    for ax, label in zip(main_axes, ['X', 'Y', 'Z', 'a', 'b', 'c']):
      ax.set_ylabel(label)
      ax.tick_params(axis='x', labelbottom=False, **common)
      ax.ticklabel_format(useOffset=False)
    self.axc.tick_params(axis='x', labelbottom=True, rotation=90)

  @property
  def color_array(self) -> List:
    """Registry-length color list with colors corresponding to plot.color.by"""
    color_by = self.parameters.plot.color.by
    color_id_map = {v: i for i, v in enumerate(self.table[color_by].unique())}
    color_ids = [color_id_map[v] for v in self.table[color_by].values]
    return [self.colormap(i % self.colormap_period) for i in color_ids]

  @property
  def x(self) -> pd.Index:
    return self.table.data.index

  @property
  def x_keys(self) -> List[str]:
    is_constant = {k: self.table[k].nunique() == 1 for k in self.order_by[1:]}
    keys_used = [self.order_by[0]]
    keys_used += [k for k in self.order_by[1:] if not is_constant[k]]
    return keys_used

  @property
  def x_label(self) -> str:
    return ':'.join(self.x_keys)

  @property
  def x_tick_labels(self) -> pd.Series:
    return self.table.data[self.x_keys].agg(':'.join, axis=1)

  def _get_handles_and_labels(self) -> Tuple[List, List]:
    handles, unique_keys = [], []
    for key in self.table[self.parameters.plot.color.by]:
      if key not in unique_keys:
        handles.append(Line2D([], [], c=self.colormap(len(unique_keys) % 10),
                              ls='', ms=12, marker='.'))
        unique_keys.append(key)
    return handles, unique_keys

  def _plot_init(self) -> None:
    self.table.sort(by=self.order_by)
    self.table_flat = self.table.flat
    self.axc.set_xlabel(self.x_label)
    self.axh.set_ylabel('# expts')

  def _plot_bars(self) -> None:
    y = self.table['expts']
    w = normalize([0, *self.table['density']])[1:]
    self.axh.bar(self.x, y, width=w, color=self.color_array, alpha=0.5)
    ax_top = self.axx.secondary_xaxis('top')
    ax_top.tick_params(rotation=90)
    ax_top.xaxis.set_major_locator(FixedLocator(self.x))
    ax_top.set_xticklabels(self.table['expts'])

  def _plot_correlations(self) -> None:
    keys = ['x', 'y', 'z', 'a', 'b', 'c']
    flat_columns = (self.table_flat[key] for key in keys)
    correlated = {col.name: col.values for col in flat_columns}
    cm = CorrelationMatrix(correlated, weights=self.table_flat['refls'])
    print(cm)
    self.axw.set_xlim([0, len(keys)])
    self.axw.set_ylim([0, len(keys)])
    for ix, kx in enumerate(keys):
      for iy, ky in enumerate(keys):
        if ix == iy:
          self.axw.text(x=ix+0.5, y=len(keys)-iy-0.5, s=kx,
                        ha='center', va='center')
        if ix > iy:
          color = self.cov_colormap(normalize([cm.corr[kx][ky], -1, 1])[0])
          r = Rectangle(xy=(ix, len(keys) - iy), width=1, height=-1, fill=True,
                        ec='white', fc=color, linewidth=2)
          self.axw.add_patch(r)

  def _plot_drift(self, axes: plt.Axes, values_key: str,
                  deltas_key: str = None) -> None:
    axes.xaxis.set_major_locator(FixedLocator(self.x))
    y = self.table[values_key]
    if not self.table.column_is_flat(values_key):
      self._plot_drift_distribution(axes, values_key)
    else:
      self._plot_drift_point(axes, y, deltas_key)
    axes.set_xticklabels(self.x_tick_labels)
    flattened_y = self.table_flat[values_key]
    flattened_weights = self.table_flat['refls']
    avg_y = average(flattened_y, weights=flattened_weights)
    if avg_y != 0:
      axes2 = axes.twinx()
      axes2.set_ylim([lim / avg_y - 1 for lim in axes.get_ylim()])
      axes2.yaxis.set_major_formatter(PercentFormatter(xmax=1))

  def _plot_drift_point(self, axes: plt.Axes, y: Sequence,
                        deltas_key: str = None) -> None:
    axes.scatter(self.x, y, c=self.color_array)
    y_err = self.table.get(deltas_key, [])
    axes.errorbar(self.x, y, yerr=y_err, ecolor='black', ls='')

  def _plot_drift_distribution(self, axes: plt.Axes, values_key: str) -> None:
    x = self.table_flat['original_index']
    y = self.table_flat[values_key]
    b = (len(self.x), 100)
    r = [[-0.5, len(self.x) - 0.5], [min(y), max(y)]]
    axes.hist2d(x, y, bins=b, range=r, cmap=plt.cm.magma_r, cmin=0.5)  # noqa
    axes.scatter(self.x, [average(val) for val in self.table[values_key]],
                 c=self.color_array, edgecolors='white')

  def _plot_legend(self) -> None:
    handles, labels = self._get_handles_and_labels()
    self.axl.legend(handles, labels, loc=7)

  def _plot_width_info(self) -> None:
    expt_lens = self.table['expts']
    refl_lens = self.table['refls'] if self.table.column_is_flat('refls') \
      else [sum(refl) for refl in self.table['refls']]
    s = f"#expts/chunk: {min(expt_lens)} - {max(expt_lens)}\n" \
        f"#refls/chunk: {min(refl_lens)} - {max(refl_lens)}"
    self.axl.text(x=0.5, y=0., s=s, clip_on=False, ha='center',
                  ma='center', va='top', transform=self.axl.transAxes)

  def plot(self) -> None:
    if len(self.table):
      self._plot_init()
      self._plot_bars()
      self._plot_correlations()
      self._plot_drift(self.axx, 'x', 'delta_x')
      self._plot_drift(self.axy, 'y', 'delta_y')
      self._plot_drift(self.axz, 'z', 'delta_z')
      self._plot_drift(self.axa, 'a', 'delta_a')
      self._plot_drift(self.axb, 'b', 'delta_b')
      self._plot_drift(self.axc, 'c', 'delta_c')
      self._plot_width_info()
      self._plot_legend()
    self.fig.align_labels()
    if self.parameters.plot.save:
      self.fig.set_size_inches(self.parameters.plot.width,
                               self.parameters.plot.height)
      self.fig.savefig(self.parameters.plot.path)
    if self.parameters.plot.show:
      plt.show()


################################ ENTRY POINTS #################################


def run(params_):
  dt = DriftTable()
  ds = DriftScraperFactory.get_drift_scraper(table=dt, parameters=params_)
  da = DriftArtist(table=dt, parameters=params_)
  ds.scrap()
  print(dt)
  da.plot()


params = []
if __name__ == '__main__':
  if '--help' in sys.argv[1:] or '-h' in sys.argv[1:]:
    print(message)
    exit()
  params = params_from_phil(sys.argv[1:])
run(params)
