from __future__ import division
import sys
from libtbx import group_args
from cctbx import maptbx
import iotbx.phil
from libtbx import adopt_init_args
from cctbx.maptbx import resolution_from_map_and_model
from libtbx import group_args
from cctbx import miller, adptbx
from mmtbx import masks
from scitbx.array_family import flex
import time
from libtbx import introspection
from libtbx.str_utils import size_as_string_with_commas

def show_process_info(out):
  print >> out, "\\/"*39
  introspection.virtual_memory_info().show_if_available(out=out, show_max=True)
  print >> out, "/\\"*39
  out.flush()

master_params_str = """
  scattering_table = wk1995  it1992  n_gaussian  neutron *electron
    .type = choice
    .help = Scattering table (X-ray, neutron or electron)
  compute {
    map_counts = True
      .type = bool
      .help = Compute map counts
    fsc_curve_model = True
      .type = bool
      .help = Compute model-map CC in reciprocal space: FSC(model map, data map)
    d_fsc_model_05 = True
      .type = bool
      .help = Compute d_fsc_model (FSC=0.5)
    d_fsc_model_0 = True
      .type = bool
      .help = Compute d_fsc_model (FSC=0)
    d_fsc_model_0143 = True
      .type = bool
      .help = Compute d_fsc_model (FSC=0.143)
    d_model = True
      .type = bool
      .help = Resolution estimate using model and map
    d_model_b0 = True
      .type = bool
      .help = Resolution estimate using model and map, assumin all atoms B=0
    d99 = True
      .type = bool
      .help = Resolution estimate d99
  }
  resolution = None
    .type = float
    .help = Map resolution (d_FSC)
  mask_maps = None
    .type = bool
    .help = Mask out region outside molecule
  radius_smooth = None
    .type = float
    .help = Mask smoothing radius
    .short_caption = Mask smoothing radius
  nproc = 1
    .type = int
    .help = Number of processors to use
  show_time = False
    .type = bool
    .help = Show individual run times for each step
  include_curves = True
    .type = bool
  include_mask = True
    .type = bool
  use_box = True
    .type = bool
    .help = Extract box from map and model and use it for calculations
"""

def get_fsc(map_data, model, params):
  result = None
  if(params.compute.fsc):
    mtriage_params = master_params().extract()
    mtriage_params.scattering_table = params.scattering_table
    mtriage_params.compute.map_counts = False
    mtriage_params.compute.fsc_curve_model = True
    mtriage_params.compute.d_fsc_model_05 = False
    mtriage_params.compute.d_fsc_model_0 = False
    mtriage_params.compute.d_fsc_model_0143 = False
    mtriage_params.compute.d_model = False
    mtriage_params.compute.d_model_b0 = False
    mtriage_params.compute.d99 = False
    mtriage_params.mask_maps = True
    mtriage_params.resolution = params.resolution
    result = mtriage(
      map_data       = map_data,
      xray_structure = model.get_xray_structure(),
      params         = mtriage_params).get_results().masked.fsc_curve_model
  return result

def get_atom_radius(xray_structure=None, resolution=None, radius=None):
  if(radius is not None): return radius
  radii = []
  if(resolution is not None):
    radii.append(resolution)
  if(xray_structure is not None and resolution is not None):
    b_iso = adptbx.u_as_b(
      flex.mean(xray_structure.extract_u_iso_or_u_equiv()))
    o = maptbx.atom_curves(scattering_type="C", scattering_table="electron")
    rad_image = o.image(d_min=resolution, b_iso=b_iso,
      radius_max=max(15.,resolution), radius_step=0.01).radius
    radii.append(rad_image)
  return max(3, min(10, max(radii)))

def master_params():
  return iotbx.phil.parse(master_params_str, process_includes=False)

class caller(object):
  def __init__(self, show=False):
    self.time_cumulative = 0
    self.show=show

  def call(self, f, msg):
    t0 = time.time()
    f()
    sa=size_as_string_with_commas(
      introspection.virtual_memory_info().current_max_sizes().virtual_memory)
    if(self.show):
      delta = time.time()-t0
      self.time_cumulative += delta
      print "%6.2f %8.2f %15s:"%(delta, self.time_cumulative, sa), msg
      sys.stdout.flush()

class mtriage(object):
  def __init__(self,
               map_data,
               map_data_1       = None,
               map_data_2       = None,
               xray_structure   = None,
               crystal_symmetry = None,
               params           = None):
    assert [xray_structure, crystal_symmetry].count(None) == 1
    self.map_data   = map_data.deep_copy()
    self.map_data_1 = None
    self.map_data_2 = None
    if(map_data_1 is not None): self.map_data_1 = map_data_1.deep_copy()
    if(map_data_2 is not None): self.map_data_2 = map_data_2.deep_copy()
    self.xray_structure   = xray_structure
    self.crystal_symmetry = crystal_symmetry
    self.params           = params
    self.results_masked   = None
    self.results_unmasked = None
    self.time_cumulative  = 0
    if(self.params is None):
      self.params = master_params().extract()
    self.caller = caller(show=self.params.show_time)

  def call(self, func, prefix):
    t0 = time.time()
    result = func()
    sa=size_as_string_with_commas(
      introspection.virtual_memory_info().current_max_sizes().virtual_memory)
    if(self.params.show_time):
      delta = time.time()-t0
      self.time_cumulative += delta
      print "%6.2f %8.2f %15s:"%(delta, self.time_cumulative, sa), prefix
      sys.stdout.flush()
    return result

  def _run(self):
    if(self.params.mask_maps is None):
      # No masking
      self.params.mask_maps = False
      self.results_unmasked = _mtriage(
        map_data         = self.map_data,
        map_data_1       = self.map_data_1,
        map_data_2       = self.map_data_2,
        xray_structure   = self.xray_structure,
        crystal_symmetry = self.crystal_symmetry,
        params           = self.params,
        caller           = self.caller
      ).run().get_results(
        include_curves = self.params.include_curves,
        include_mask   = self.params.include_mask)
      # Masking
      if(self.params.radius_smooth is None):
        self.params.radius_smooth = self.results_unmasked.d99
      self.params.mask_maps = True
      self.results_masked = _mtriage(
        map_data         = self.map_data,
        map_data_1       = self.map_data_1,
        map_data_2       = self.map_data_2,
        xray_structure   = self.xray_structure,
        crystal_symmetry = self.crystal_symmetry,
        params           = self.params,
        caller           = self.caller
      ).run().get_results(
        include_curves = self.params.include_curves,
        include_mask   = self.params.include_mask)
    else:
      result = _mtriage(
        map_data         = self.map_data,
        map_data_1       = self.map_data_1,
        map_data_2       = self.map_data_2,
        xray_structure   = self.xray_structure,
        crystal_symmetry = self.crystal_symmetry,
        params           = self.params,
        caller           = self.caller
      ).run().get_results(
        include_curves = self.params.include_curves,
        include_mask   = self.params.include_mask)
      if(self.params.mask_maps): self.results_masked = result
      else:                      self.results_unmasked = result

  def get_results(self):
    self._run()
    cs = self.crystal_symmetry
    if(cs is None): cs = self.xray_structure.crystal_symmetry()
    return group_args(
      crystal_symmetry = cs,
      masked   = self.results_masked,
      unmasked = self.results_unmasked)

class _mtriage(object):
  def __init__(self,
        map_data,
        map_data_1,
        map_data_2,
        xray_structure,
        crystal_symmetry,
        caller,
        params):
    adopt_init_args(self, locals())
    assert [self.xray_structure, self.crystal_symmetry].count(None) == 1
    if(self.crystal_symmetry is None):
      self.crystal_symmetry = self.xray_structure.crystal_symmetry()
    self.call = self.caller.call
    self.resolution = self.params.resolution
    # Results
    self.d99              = None
    self.d999             = None
    self.d9999            = None
    self.d99999           = None
    self.d99_1            = None
    self.d99_2            = None
    self.d_model          = None
    self.d_model_b0       = None
    self.b_iso_overall    = None
    self.d_fsc            = None
    self.d_fsc_model_05   = None
    self.d_fsc_model_0    = None
    self.d_fsc_model_0143 = None
    self.fsc_curve        = None
    self.fsc_curve_model  = None
    self.mask_object      = None
    self.radius_smooth    = self.params.radius_smooth
    self.d_corner         = None
    self.d9999            = None
    # Info (results)
    self.map_counts        = None
    self.half_map_1_counts = None
    self.half_map_2_counts = None
    self.map_histograms    = None
    # Internal work objects
    self.f_map    = None
    self.f_map_1  = None
    self.f_map_2  = None
    self.f_calc   = None

  def run(self):
    # Compute radius
    self.call(f=self._compute_radius, msg="Compute radius")
    # Compute and apply mask
    self.call(f=self._compute_and_apply_mask, msg="Masking")
    # Compute F_maps
    self.call(f=self._compute_f_maps, msg="Compute F_maps")
    # Compute d99
    self.call(f=self._compute_d99, msg="Compute d99")
    # Strategy adjustments based on d99
    self.call(f=self._adjust, msg="Adjustments based on d99")
    # Compute half-map FSC
    self.call(f=self._compute_half_map_fsc, msg="Compute half-map FSC")
    # Compute Fcalc
    self.call(f=self._compute_f_calc, msg="Compute Fcalc")
    # Map-model FSC curve
    self.call(f=self._compute_fsc_curve_model, msg="Compute fsc_curve_model")
    # d_fsc_model_0
    self.call(f=self._compute_f_fsc_model_0, msg="Compute d_fsc_model_0")
    # d_fsc_model_0143
    self.call(f=self._compute_f_fsc_model_0143, msg="Compute d_fsc_model_0143")
    # d_fsc_model_05
    self.call(f=self._compute_f_fsc_model_05, msg="Compute d_fsc_model_05")
    # Compute d_model
    self.call(f=self._compute_d_model, msg="Compute d_model")
    return self

  def _adjust(self):
    if(self.d99>10.): # Atomic model isn't suitable?
      self.params.compute.fsc_curve_model = False
      self.params.compute.d_fsc_model_05  = False
      self.params.compute.d_fsc_model_0   = False
      self.params.compute.d_fsc_model_0143= False
      self.params.compute.d_model         = False
      self.params.compute.d_model_b0      = False

  def _compute_radius(self):
    if(not self.params.mask_maps): return
    if(self.xray_structure is None): return
    self.radius_smooth = get_atom_radius(
      xray_structure   = self.xray_structure,
      radius           = self.radius_smooth,
      resolution       = self.resolution)

  def _compute_and_apply_mask(self):
    if(not self.params.mask_maps): return
    if(self.xray_structure is None): return
    mask_smooth = masks.smooth_mask(
      xray_structure = self.xray_structure,
      n_real         = self.map_data.all(),
      rad_smooth     = self.radius_smooth).mask_smooth
    self.map_data = self.map_data*mask_smooth
    if(self.map_data_1 is not None):
      self.map_data_1 = self.map_data_1*mask_smooth
      self.map_data_2 = self.map_data_2*mask_smooth

  def _compute_f_maps(self):
    self.f_map = miller.structure_factor_box_from_map(
      map              = self.map_data,
      crystal_symmetry = self.crystal_symmetry)
    if(self.map_data_1 is not None):
      self.f_map_1 = miller.structure_factor_box_from_map(
        map              = self.map_data_1,
        crystal_symmetry = self.crystal_symmetry)
      self.f_map_2 = miller.structure_factor_box_from_map(
        map              = self.map_data_2,
        crystal_symmetry = self.crystal_symmetry)

  def _compute_d99(self):
    if(not self.params.compute.d99): return
    d99 = maptbx.d99(f_map = self.f_map)
    self.d99    = d99.result.d99
    self.d999   = d99.result.d999
    self.d9999  = d99.result.d9999
    self.d99999 = d99.result.d99999
    self.f_map = self.f_map.resolution_filter(d_min = self.d99999-0.1)
    d99_obj_1, d99_obj_2 = None,None
    if(self.map_data_1 is not None):
      d99_1 = maptbx.d99(
        map              = self.map_data_1,
        crystal_symmetry = self.crystal_symmetry)
      d99_2 = maptbx.d99(
        map              = self.map_data_2,
        crystal_symmetry = self.crystal_symmetry)
      self.d99_1 = d99_1.result.d99
      self.d99_2 = d99_2.result.d99
      self.f_map_1 = d99_1.f_map
      self.f_map_2 = d99_2.f_map

  def _compute_f_calc(self):
    if(self.xray_structure is None): return
    self.f_calc = self.f_map.structure_factors_from_scatterers(
      xray_structure = self.xray_structure).f_calc()

  def _compute_d_model(self):
    if(not self.params.compute.d_model): return
    if(self.xray_structure is not None):
      o = resolution_from_map_and_model.run(
        f_map            = self.f_map,
        d_fsc_model      = self.d_fsc_model_0,
        xray_structure   = self.xray_structure)
      self.d_model       = o.d_min
      self.b_iso_overall = o.b_iso
      self.d_model_b0    = o.d_model_b0

  def _compute_half_map_fsc(self):
    if(self.map_data_1 is not None):
      self.fsc_curve = self.f_map_1.d_min_from_fsc(
        other = self.f_map_2, bin_width=100, fsc_cutoff=0.143)
      self.d_fsc = self.fsc_curve.d_min

  def _compute_fsc_curve_model(self):
    if(not self.params.compute.fsc_curve_model): return
    if(self.xray_structure is not None):
      self.fsc_curve_model = self.f_calc.fsc(
        other=self.f_map, bin_width=100)

  def _compute_f_fsc_model_0(self):
    if(not self.params.compute.d_fsc_model_0): return
    if(self.xray_structure is None): return
    assert self.fsc_curve_model is not None
    self.d_fsc_model_0 = self.f_calc.d_min_from_fsc(
      fsc_curve=self.fsc_curve_model, fsc_cutoff=0.).d_min

  def _compute_f_fsc_model_0143(self):
    if(not self.params.compute.d_fsc_model_0143): return
    if(self.xray_structure is None): return
    assert self.fsc_curve_model is not None
    self.d_fsc_model_0143 = self.f_calc.d_min_from_fsc(
      fsc_curve=self.fsc_curve_model, fsc_cutoff=0.143).d_min

  def _compute_f_fsc_model_05(self):
    if(not self.params.compute.d_fsc_model_05): return
    if(self.xray_structure is None): return
    assert self.fsc_curve_model is not None
    self.d_fsc_model_05 = self.f_calc.d_min_from_fsc(
      fsc_curve=self.fsc_curve_model, fsc_cutoff=0.5).d_min

  def get_results(self, include_curves, include_mask):
    mask = None
    if(self.mask_object is not None and include_mask):
      mask = self.mask_object.mask_smooth
    map_histograms  = None
    fsc_curve       = None
    fsc_curve_model = None
    if(include_curves):
      map_histograms  = self.map_histograms
      fsc_curve       = self.fsc_curve
      fsc_curve_model = self.fsc_curve_model
    return group_args(
      d99               = self.d99,
      d999              = self.d999,
      d9999             = self.d9999,
      d99999            = self.d99999,
      d99_1             = self.d99_1,
      d99_2             = self.d99_2,
      d_model           = self.d_model,
      d_model_b0        = self.d_model_b0,
      b_iso_overall     = self.b_iso_overall,
      d_fsc             = self.d_fsc,
      d_fsc_model_05    = self.d_fsc_model_05,
      d_fsc_model_0     = self.d_fsc_model_0,
      d_fsc_model_0143  = self.d_fsc_model_0143,
      fsc_curve         = fsc_curve,
      fsc_curve_model   = fsc_curve_model,
      mask              = mask,
      radius_smooth     = self.radius_smooth)

if (__name__ == "__main__"):
  run(args=sys.argv[1:])
