
# LIBTBX_SET_DISPATCHER_NAME cctbx.xfel.candidate_cells
from __future__ import division
from iotbx.phil import parse
from dials.util.options import ArgumentParser
from cctbx import uctbx, miller, crystal
from libtbx import easy_mp
from cctbx.uctbx import d_as_d_star_sq, d_star_sq_as_two_theta
from cctbx import miller, crystal, sgtbx, uctbx
import functools

conda_message = """
GSASII is required and must be installed manually. Follow the steps in the
small_cell documentation at:

  https://github.com/cctbx/cctbx_project/tree/master/xfel/small_cell
"""

try:
  import GSASIIindex as gi
except ImportError:
  print(conda_message)
  exit()

help_message = """
Script to generate candidate unit cells from a list of measured d-spacings
Example usage:
cctbx.xfel.candidate_cells nproc=64 input.peak_list=mithrene_peaks.txt \\
  input.powder_pattern=mithrene_powder.xy search.timeout=300

This uses the SVD-Index powder indexing algorithm of Coelho
(https://doi.org/10.1107/S0021889802019878) as implemented in GSAS-II (Toby and
Von Dreele, https://doi.org/10.1107/S0021889813003531) to generate possible unit
cells. Candidates are ranked by their agreement with the peak list and, if
available, a full powder pattern. These peaks and powder pattern may be prepared
conveniently using cctbx.xfel.powder_from_spots.

Test data are available in xfel_regression/small_cell_data. The command given
above should run in 5 minutes on a 64-core machine.
"""


phil_scope = parse(
    """
  search {
    n_searches = 2 2 2 4 4 4 4 6 6 6 6 16 16 24
      .type = ints(size=14)
      .help = "Number of GSASIIindex runs per lattice type. Given in order cF,"
              "cI, cP, hR, hP, tI, tP, oF, oI, oC, oP, mC, mP, aP."
    n_peaks = 20
      .type = int
      .help = "Number of d-spacings for unit cell search. If the peak list"
              "given by input.peak_list is longer than n_peaks, a random subset"
              "is selected for each GSASIIindex run."
    timeout = 300
      .type = int
      .help = "Timeout the GSASII lattice search calls after this many seconds"
    m20_min = 10.0
      .type = float
      .help = "Ignore search hits with an M20 figure of merit smaller than this"
    x20_max = 2
      .type = int
      .help = "Ignore search hits with more than this many unindexed peaks"
  }

  multiprocessing {
    nproc = 1
      .type = int
  }

  validate {
    d_min = 2
      .type = float
  }

  input {
    peak_list = None
      .type = str
      .help = "a list of d-spacings, 1 per line"
    powder_pattern = None
      .type = str
      .help = "A powder pattern in .xy format for validation of candidate cells"
  }
    """
)

class Candidate_cell(object):
  def __init__(self, cs, npeaks=None, m20=None):
    '''
    Constructed from an instance of cctbx.crystal.symmetry. Optionally, npeaks
    is the GSASIIindex quantity Nc, which is the number of peaks generated by
    this cell and lattice within a given resolution limit.
    '''
    self.cs = cs
    self.niggli_uc = cs.niggli_cell().unit_cell()
    self.npeaks = npeaks
    self.m20 = m20

  def __str__(self):
    uc = self.cs.best_cell().best_cell().best_cell().best_cell().unit_cell()
    return "{}\t{}".format(str(uc), str(self.sg.info()))

  def standardize(self):
    # cs.best_cell is really more like "better cell" so we call it a few
    # times to ensure we get the actual best cell
    self.cs = self.cs.best_cell().best_cell().best_cell().best_cell()

  def matches_cell(self, cell2):
    nc1 = self.niggli_uc
    nc2 = cell2.niggli_uc
    return nc1.similarity_transformations(nc2).size() > 0

  def calc_powder_score(self, powder_pattern, d_min):
    '''Take a list of (d, counts) tuples and return a figure of merit (lower-better)
    '''
    if powder_pattern is None: return 100
    assert self.sg is not None
    mig = miller.index_generator(self.uc, self.sg.type(), 0, 0.8*d_min)
    d_spacings = []
    for h in mig: d_spacings.append(self.uc.d(h))

    error_cumul = 0
    for x, y in powder_pattern:
      if x < d_min: break
      best_match = min(d_spacings, key=lambda d: abs(x-d))
      error = abs(x-best_match)/x
      error_cumul += error*y

    return error_cumul

  def save_powder_score(self, powder_pattern, d_min):
    self.powder_score = self.calc_powder_score(powder_pattern, d_min)

  @property
  def score(self):
    return self.powder_score/self.m20


  @property
  def uc(self):
    return self.cs.unit_cell()

  @property
  def sg(self):
    return self.cs.space_group()

class Candidate_cell_manager(object):
  def __init__(self):
    self.cells = []
    self.min_score = 0

  def maintain(self, force=False):
    if len(self.cells) > 30 or force:
      self.cells.sort(key=lambda x: x.cumul_score, reverse=True)
      self.cells = self.cells[:20]
      self.min_score = min([c.average_score() for c in self.cells])

  def store_cell(self,gcell):
    self.maintain()
    uc = uctbx.unit_cell(gcell[3:9])
    score = Candidate_cell.hit_score(gcell)
    if score > self.min_score:
      found_match = False
      for cell in self.cells:
        if cell.matches_cell(uc):
          cell.store_hit(gcell)
          found_match = True
          break
      if not found_match:
        self.cells.append(Candidate_cell(gcell))

def gpeak_from_d_spacing(d, wavl):
  """take a d-spacing and return a peak in GSASII format"""
  twoth = d_star_sq_as_two_theta(d_as_d_star_sq(d), wavl, deg=True)
  return [twoth, 1000, True, False, 0, 0, 0, d, 0]

def prepare_gpeaks(d_spacings, wavl, n_peaks=None):
  if n_peaks is not None:
    assert len(d_spacings) >= n_peaks
    trial_set = sorted(random.sample(d_spacings, n_peaks), reverse=True)
  else:
    trial_set = sorted(d_spacings, reverse=True)
  trial_gpeaks = [gpeak_from_d_spacing(d, wavl) for d in trial_set]
  return trial_gpeaks

def call_gsas(args):
  '''
  '''

  def _make_cctbx_args(sg_string):
    return {
        'sg_type': sgtbx.space_group_type(sg_string),
        'uctbx_unit_cell': uctbx.unit_cell,
        'miller_index_generator': miller.index_generator
        }


  # These are the full lists of lattice types that GSASII knows about, and some
  # corresponding symmorphic space groups. We don't search for all of these,
  # instead only the subset given as Script.lattice_symbols.
  symmorphic_sgs = ['F23', 'I23', 'P23', 'R3', 'P3', 'I4', 'P4', 'F222', 'I222',
      'A222', 'B222', 'C222', 'P222', 'I2', 'A2', 'C2', 'P2', 'P1']
  lattices = ['cF', 'cI', 'cP', 'hR', 'hP', 'tI', 'tP', 'oF', 'oI', 'oA', 'oB',
      'oC', 'oP', 'mI', 'mA', 'mC', 'mP', 'aP']

  #d_spacings, bravais, powder_pattern, d_min, wavl, timeout = args
  params, bravais, d_spacings, powder_pattern = args

  d_min = params.validate.d_min
  wavl = 1.0 # GSASII does not use this
  timeout = params.search.timeout
  m20_min = params.search.m20_min
  x20_max = params.search.x20_max

  i_bravais = lattices.index(bravais)
  sg_string = symmorphic_sgs[i_bravais]
  bravais_list = [i==i_bravais for i in range(18)]

  cctbx_args = _make_cctbx_args(sg_string)

  #TODO: adaptively set starting volume controls[3] based on number of peaks
  controls = [0, 0.0, 4, 200, 0, 'P1', 1.0, 1.0, 1.0, 90.0, 90.0, 90.0, 1.0,
      'P 1', []]

  trial_gpeaks = prepare_gpeaks(d_spacings, wavl)


  try:
    success, dmin, gcells = gi.DoIndexPeaks(
        trial_gpeaks,
        controls,
        bravais_list,
        None,
        timeout=timeout,
        M20_min=m20_min,
        X20_max=x20_max,
        return_Nc=True,
        cctbx_args=cctbx_args)
  except FloatingPointError: #this raises "invalid value encountered in double_scalars" sometimes
    print("############################################################\n"*10,
        "crash in search for {}".format(bravais))
    return []

  candidates = []
  for gcell in gcells:
    m20 = gcell[0]
    ibrav = gcell[2]
    uc = gcell[3:9]
    npeaks = gcell[12]
    sg = symmorphic_sgs[ibrav]
    cs = crystal.symmetry(unit_cell=uc, space_group_symbol=sg)
    candidate = Candidate_cell(cs, npeaks, m20)
    candidate.save_powder_score(powder_pattern, d_min)
    candidates.append(candidate)
  return candidates

def i_first_matching(cand1, cand_list):
  '''
  Given a candidate cand1 and a list of candidates, return the index of the
  first candidate in the list with a unit cell matching cand1.
  '''
  for i_cand, cand2 in enumerate(cand_list):
    if cand1.matches_cell(cand2):
      return i_cand
  raise RuntimeError

def print_results(candidates, params):
  '''
  Take a list of candidates and sort into groups with matching unit cells. For
  each group, assign it the cell parameters of the cell giving the best score.
  Sort groups by score and print the scores and cell parameters.
  '''
  i_first_matching_partial = functools.partial(
      i_first_matching, cand_list=candidates)
  i_first_matching_list = easy_mp.parallel_map(
      i_first_matching_partial,
      candidates,
      processes=params.multiprocessing.nproc)

  i_first_matching_unique = set(i_first_matching_list)
  results = []
  for i in i_first_matching_unique:
    matches = [
        cand
        for i_cand, cand in enumerate(candidates)
        if i == i_first_matching_list[i_cand]
        ]
    best = min(matches, key=lambda m:m.score)
    results.append(best)
  results.sort(key=lambda r: r.score)
  for r in results[:10]:
    print("{:.4f}\t{}".format(r.score, r))

class Script(object):
  def __init__(self):
    usage = None
    self.parser = ArgumentParser(
         usage=usage,
         phil=phil_scope,
         epilog=help_message,
         check_format=False,
         read_reflections=True,
         read_experiments=True,
         )

  def run(self):

    params, options = self.parser.parse_args()

    # Load d-spacings and powder pattern from files
    with open(params.input.peak_list) as f:
      d_spacings = [float(l.strip()) for l in f.readlines()]
    if params.input.powder_pattern is not None:
      with open(params.input.powder_pattern) as f:
        powder_pattern = []
        for l in f.readlines():
          x, y = l.split()
          powder_pattern.append((float(x), float(y)))
    else:
      powder_pattern = None

    d_min = params.validate.d_min
    timeout = params.search.timeout

    lattices_todo = []
    lattice_symbols = ['cF', 'cI', 'cP', 'hR', 'hP', 'tI', 'tP', 'oF', 'oI',
        'oC', 'oP', 'mC', 'mP', 'aP']
    for l, n in zip(lattice_symbols, params.search.n_searches):
      lattices_todo.extend([l] * n)
    lattices_todo.reverse() # we want to start the longer jobs right away

    candidates = easy_mp.parallel_map(
        call_gsas,
        [(params, bravais, d_spacings, powder_pattern)
            for bravais in lattices_todo],
        processes=params.multiprocessing.nproc)

    n_triclinic = params.search.n_searches[-1]
    candidates_triclinic_flat = []
    for c in candidates[:n_triclinic]: candidates_triclinic_flat.extend(c)
    candidates_other_flat = []
    for c in candidates[n_triclinic:]: candidates_other_flat.extend(c)

    print("Monoclinic and higher results:")
    print_results(candidates_other_flat, params)
    print("Triclinic results:")
    print_results(candidates_triclinic_flat, params)

if __name__=="__main__":
  script = Script()
  script.run()
