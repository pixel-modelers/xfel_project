from __future__ import absolute_import,division, print_function
from io import StringIO
import time
import os

from libtbx import Auto
from libtbx.str_utils import make_header
from libtbx.utils import Sorry
from libtbx.utils import null_out
from libtbx import group_args
from cctbx.geometry_restraints.manager import manager as standard_manager
from cctbx.array_family import flex
from mmtbx.geometry_restraints import quantum_interface
from mmtbx.geometry_restraints import qm_manager
from mmtbx.geometry_restraints import mopac_manager
from mmtbx.geometry_restraints import orca_manager

from mmtbx.model.restraints import get_restraints_from_model_via_grm

import iotbx
get_class = iotbx.pdb.common_residue_names_get_class

from scitbx.matrix import col

WRITE_STEPS_GLOBAL=False

def dist2(r1,r2): return (r1[0]-r2[0])**2+(r1[1]-r2[1])**2+(r1[2]-r2[2])**2
def min_dist2(residue_group1, residue_group2, limit=1e-2):
  min_d2=1e9
  min_ca_d2=1e9
  for atom1 in residue_group1.atoms():
    for atom2 in residue_group2.atoms(): # ligand but could be more than one rg!!!
      d2 = dist2(atom1.xyz, atom2.xyz)
      if d2<limit and min_ca_d2<1e9: return d2, min_ca_d2
      min_d2 = min(min_d2, d2)
      if atom1.name.strip()=='CA':
        min_ca_d2 = min(min_ca_d2, d2)
  return min_d2, min_ca_d2

class manager(standard_manager):
  def __init__(self,
               params,
               log=StringIO()
               ):
    pass

  def __repr__(self):
    return 'QM restraints manager'

  def cleanup(self, log=StringIO()):
    make_header('Cleaning up - QM restraints', out=log)
    assert 0

def digester(model,
             standard_geometry_restraints_manager,
             params,
             log=StringIO(),
             ):
  #
  # Digest
  #
  sgrm = standard_geometry_restraints_manager
  qm_grm = manager(params, log=log)
  for attr, value in list(vars(sgrm).items()):
    if attr.startswith('__'): continue
    setattr(qm_grm, attr, value)
  qm_grm.standard_geometry_restraints_manager = sgrm
  #
  make_header('QM Restraints Initialisation', out=log)
  qm_restraints_initialisation(params, log=log)
  run_program=True
  for i, qmr in enumerate(params.qi.qm_restraints):
    if qmr.run_in_macro_cycles=='test': break # REMOVE AFTER TESTING!!!
  else: run_program=False
  run_energies(model,
               params,
               run_program=run_program,
               # transfer_internal_coordinates=transfer_internal_coordinates,
               log=log,
              )
  return qm_grm

def get_prefix(params):
  if hasattr(params, 'output') and hasattr(params.output, 'prefix'):
    prefix = params.output.prefix
  else:
    prefix = 'qmr'
  return prefix

def write_pdb_file(model, filename, log=None):
  outl = model.model_as_pdb()
  print('    Writing PDB : %s' % filename, file=log)
  f=open(filename, 'w')
  f.write(outl)
  del f

def write_restraints(model, filename, header=None, log=None):
  """Write restraints from a model

  Args:
      model (model class): Model with one entity and no alt. loc.
      filename (TYPE): Description
      log (None, optional): Description

  """
  try:
    co = get_restraints_from_model_via_grm(model, ideal=False)
  except AssertionError:
    print('\n  Failed to write restraints', file=log)
    return
  print('\n  Writing restraints : %s' % filename, file=log)
  f=open(filename, 'w')
  if header:
    for line in header.splitlines():
      if not line.startswith('#'):
        line = '# %s' % line
      f.write('%s\n' % line)
  f.write(str(co))
  del f

def add_additional_hydrogen_atoms_to_model( model,
                                            use_capping_hydrogens=False,
                                            # use_neutron_distances=True,
                                            retain_original_hydrogens=True,
                                            append_to_end_of_model=False,
                                            n_terminal_charge=True,
                                            ):
  from mmtbx.ligands.ready_set_utils import add_terminal_hydrogens
  from mmtbx.ligands.ready_set_utils import add_water_hydrogen_atoms_simple
  from mmtbx.ligands.ready_set_utils import delete_charged_n_terminal_hydrogens
  rc = add_terminal_hydrogens( model.get_hierarchy(),
                               model.get_restraints_manager().geometry,
                               use_capping_hydrogens=use_capping_hydrogens,
                               retain_original_hydrogens=retain_original_hydrogens,
                               append_to_end_of_model=append_to_end_of_model,
                               )
  assert not rc
  rc = add_water_hydrogen_atoms_simple(model.get_hierarchy())
  if not n_terminal_charge:
    rc = delete_charged_n_terminal_hydrogens(model.get_hierarchy())
  hierarchy = model.get_hierarchy()
  for i, atom in enumerate(hierarchy.atoms()):
    if i and not atom.tmp: atom.tmp=-1

def select_and_reindex(model,
                       selection_str=None,
                       selection_array=None,
                       reindex=True,
                       verbose=False):
  from scitbx_array_family_flex_ext import reindexing_array
  def _reindexing(mod, sel, verbose=False):
    isel = sel.iselection()
    ra = reindexing_array(len(sel),
                          flex.size_t(isel).as_int())
    atoms = mod.get_atoms()
    for i_seq in isel:
      atoms[ra[i_seq]].tmp=i_seq
    if verbose:
      for atom in mod.get_atoms():
        print(atom.quote(), atom.i_seq, atom.tmp)
    return mod
  assert (selection_array, selection_str).count(None)==1
  if selection_str:
    selection_array = model.selection(selection_str)
  selected_model = model.select(selection_array)
  if reindex:
    rc = _reindexing(selected_model, selection_array, verbose=verbose)
  return selected_model

def super_cell_and_prune(buffer_model,
                         ligand_model,
                         buffer,
                         prune_limit=5.,
                         do_not_prune=False,
                         write_steps=False):
  from cctbx.crystal import super_cell
  def find_movers(buffer_model, ligand_model, buffer, prune_limit=5.):
    buffer*=buffer
    prune_limit*=prune_limit
    movers = []
    close = []
    removers = []
    same = []
    prune_main = []
    for residue_group1 in buffer_model.get_hierarchy().residue_groups():
      for residue_group2 in ligand_model.get_hierarchy().residue_groups():
        if residue_group1.id_str()==residue_group2.id_str():
          same.append(residue_group1)
          continue
        if list(residue_group1.unique_resnames())==list(residue_group2.unique_resnames()):
          min_d2, min_ca_d2 = min_dist2(residue_group1, residue_group2, limit=.1)
          if min_d2<=.1:
            removers.append(residue_group1)
        else:
          min_d2, min_ca_d2 = min_dist2(residue_group1, residue_group2, limit=buffer)
        if min_d2<=buffer:
          close.append(residue_group1)
        else:
          movers.append(residue_group1)
        if min_ca_d2 is not None and min_ca_d2>prune_limit:
          prune_main.append(residue_group1)
      assert residue_group1 in movers or residue_group1 in close or residue_group1 in same
    for chain in buffer_model.get_hierarchy().chains():
      if do_not_prune: break
      for rg in movers+removers:
        if rg in chain.residue_groups():
          chain.remove_residue_group(rg)
    # if prune_main: prune_main_chain(residue_group1, prune_main)
    return movers, removers
  def prune_main_chain(residue_group1, prune_main):
    mainchain = ['N', 'CA', 'C', 'O', 'OXT', 'H', 'HA', 'H1', 'H2', 'H3']
    for residue_group1 in prune_main:
      ur = residue_group1.unique_resnames()
      if 'PRO' in ur or 'GLY' in ur:
        if list(ur)==['PRO']:
          assert 0
        continue
      cb_atom = None
      for atom in residue_group1.atoms():
        if atom.name.strip()=='CB':
          cb_atom=atom
          break
      if cb_atom is None: continue
      pruning=False
      for atom in residue_group1.atoms():
        if atom.name.strip()=='CA':
          atom.name=' HBC'
          atom.element='H'
          atom.xyz = ((atom.xyz[0]+cb_atom.xyz[0])/2,
                      (atom.xyz[1]+cb_atom.xyz[1])/2,
                      (atom.xyz[2]+cb_atom.xyz[2])/2,
                      )
          pruning=True
          break
      if pruning:
        for atom in residue_group1.atoms():
          if atom.name.strip() in mainchain:
              ag = atom.parent()
              ag.remove_atom(atom)

  complete_p1 = super_cell.run(
    pdb_hierarchy        = buffer_model.get_hierarchy(),
    crystal_symmetry     = buffer_model.crystal_symmetry(),
    select_within_radius = buffer,
    )
  if(write_steps):
    complete_p1.hierarchy.write_pdb_file(file_name="complete_p1.pdb",
      crystal_symmetry = complete_p1.crystal_symmetry)
  for atom in complete_p1.hierarchy.atoms(): atom.tmp=-1
  for atom1, atom2 in zip(buffer_model.get_atoms(), complete_p1.hierarchy.atoms()):
    atom2.tmp = atom1.tmp
  buffer_model._pdb_hierarchy = complete_p1.hierarchy
  movers, removers = find_movers(buffer_model, ligand_model, buffer)
  assert len(buffer_model.get_atoms())>0

def use_neutron_distances_in_model_in_place(model):
  """Changes the X-H distances in place

  Args:
      model (model): model
  """
  params = model.get_current_pdb_interpretation_params()
  params.pdb_interpretation.use_neutron_distances = True
  model.log=null_out()
  model.process(make_restraints           = True,
                pdb_interpretation_params = params)
  model.set_hydrogen_bond_length(show=False)

def reverse_shift(original_model, moved_model):
  from scitbx.matrix import col
  ph=original_model.get_hierarchy()
  sites_cart=ph.atoms().extract_xyz()
  box_cushion = sites_cart.min()
  ph=moved_model.get_hierarchy()
  sites_cart=ph.atoms().extract_xyz()
  translate = sites_cart.min()
  sites_cart=sites_cart+col(box_cushion)-col(translate)
  ph.atoms().set_xyz(sites_cart)

def get_ligand_buffer_models(model, qmr, verbose=False, write_steps=False):
  if WRITE_STEPS_GLOBAL: write_steps=True
  ligand_model = select_and_reindex(model, qmr.selection)
  #
  # check for to sparse selections like a ligand in two monomers
  #
  if len(ligand_model.get_atoms())==0:
    raise Sorry('selection "%s" results in empty model' % qmr.selection)
  if write_steps: write_pdb_file(ligand_model, 'model_selection.pdb', None)
  assert qmr.selection.find('within')==-1
  if qmr.buffer_selection:
    buffer_selection_string = qmr.buffer_selection
  else:
    buffer_selection_string = 'residues_within(%s, %s)' % (qmr.buffer,
                                                           qmr.selection)
  buffer_model = select_and_reindex(model, buffer_selection_string)
  if write_steps: write_pdb_file(buffer_model, 'pre_remove_altloc.pdb', None)
  buffer_model.remove_alternative_conformations(always_keep_one_conformer=True)
  if write_steps: write_pdb_file(buffer_model, 'post_remove_altloc.pdb', None)
  for residue_group in buffer_model.get_hierarchy().residue_groups():
    if (residue_group.atom_groups_size() != 1):
      raise Sorry("Not implemented: cannot run QI on buffer "+
                  "molecules with alternate conformations")
  for atom_group in buffer_model.get_hierarchy().atom_groups():
    if get_class(atom_group.resname) in ["common_rna_dna",
                                         "modified_rna_dna",
                                         "ccp4_mon_lib_rna_dna"]:
      raise Sorry('QI cannot protonate RNA/DNA : "%s"' % atom_group.id_str())
  if write_steps: write_pdb_file(buffer_model, 'pre_super_cell.pdb', None)
  do_not_prune = qmr.buffer_selection
  super_cell_and_prune(buffer_model,
                       ligand_model,
                       qmr.buffer,
                       do_not_prune=do_not_prune,
                       write_steps=write_steps)
  if write_steps: write_pdb_file(buffer_model, 'post_super_cell.pdb', None)

  buffer_model.unset_restraints_manager()
  buffer_model.log=null_out()
  if write_steps: write_pdb_file(buffer_model, 'pre_add_terminii.pdb', None)
  buffer_model.process(make_restraints=True)
  add_additional_hydrogen_atoms_to_model(buffer_model,
                                         use_capping_hydrogens=qmr.capping_groups)
  buffer_model.unset_restraints_manager()
  buffer_model.log=null_out()
  if write_steps: write_pdb_file(buffer_model, 'post_add_terminii.pdb', None)
  buffer_model.process(make_restraints=True)
  ligand_atoms = ligand_model.get_atoms()
  buffer_atoms = buffer_model.get_atoms()
  def compare_id_str(s1,s2):
    ptr=9
    if s1[:ptr]==s2[:ptr] and s1[ptr+1:]==s2[ptr+1:]:
      return True
    return False
  for atom1 in ligand_atoms:
    for atom2 in buffer_atoms:
      if compare_id_str(atom1.id_str(), atom2.id_str()):
        break
    else:
      raise Sorry('''Bug alert
  Atom %s from ligand does not appear in buffer. Contact Phenix with input files.
  ''' % atom1.quote())
  #
  # necessary for amino acid selections to calculate energies
  #
  # ligand_model.unset_restraints_manager()
  # ligand_model.log=null_out()
  # ligand_model.process(make_restraints=True)
  # add_additional_hydrogen_atoms_to_model(ligand_model,
  #                                        use_capping_hydrogens=qmr.capping_groups)
  # ligand_model.unset_restraints_manager()
  # ligand_model.log=null_out()
  # ligand_model.process(make_restraints=True)
  #
  # reverse_shift(original_model, buffer_model_p1)
  def move_atoms(local_model):
    ph=local_model.get_hierarchy()
    sites_cart=ph.atoms().extract_xyz()
    sites_cart=sites_cart-col(box)+col(mc)
    ph.atoms().set_xyz(sites_cart)
  # move_atoms(buffer_model)
  # move_atoms(ligand_model)
  if write_steps: write_pdb_file(buffer_model, 'post_reverse_shift.pdb', None)
  use_neutron_distances_in_model_in_place(ligand_model)
  use_neutron_distances_in_model_in_place(buffer_model)
  if write_steps:
    write_pdb_file(buffer_model, 'post_neutron_cluster.pdb', None)
    write_pdb_file(ligand_model, 'post_neutron_ligand.pdb', None)
  return ligand_model, buffer_model

def show_ligand_buffer_models(ligand_model, buffer_model):
  outl = '    Core atoms\n'
  ags = []
  for atom in ligand_model.get_atoms():
    outl += '      %s (%5d)\n' % (atom.id_str().replace('pdb=',''), atom.tmp)
  for atom in buffer_model.get_atoms():
    agi = atom.parent().id_str()
    if agi not in ags: ags.append(agi)
  outl += '    Buffer residues\n'
  for agi in ags:
    outl += '      %s\n' % agi
  return outl

def get_specific_atom_charges(qmr):
  rc=[]
  sacs = qmr.specific_atom_charges
  for sac in sacs:
    rc.append(sac)
  return rc

def get_qm_manager(ligand_model, buffer_model, qmr, program_goal, log=StringIO()):
  program = qmr.package.program
  if program=='test':
    qmm = qm_manager.base_qm_manager.base_qm_manager
  elif program=='orca':
    qmm = orca_manager.orca_manager
  elif program=='mopac':
    qmm = mopac_manager.mopac_manager
  else:
    assert 0
  qmr = quantum_interface.populate_qmr_defaults(qmr)

  electron_model = None
  solvent_model = qmr.package.solvent_model
  if program_goal in ['energy', 'strain']:
    electron_model = ligand_model
    solvent_model = 'EPS=78.4 PRECISE NSPA=92'
  elif program_goal in ['opt', 'bound']:
    electron_model = buffer_model
  else:
    assert 0, 'program_goal %s not in list' % program_goal
  # specific_atom_charges = get_specific_atom_charges(qmr)
  specific_atom_charges = qmr.specific_atom_charges
  total_charge = quantum_interface.electrons(
    electron_model,
    specific_atom_charges=specific_atom_charges,
    log=log)
  if total_charge!=qmr.package.charge:
    print(u'  Update charge %s ~> %s' % (qmr.package.charge, total_charge),
          file=log)
    qmr.package.charge=total_charge
  qmm = qmm(electron_model.get_atoms(),
            qmr.package.method,
            qmr.package.basis_set,
            solvent_model,
            qmr.package.charge,
            qmr.package.multiplicity,
            qmr.package.nproc,
            # preamble='%02d' % (i+1),
            )
  qmm.program=program
  qmm.program_goal=program_goal
  ligand_i_seqs = []
  for atom in ligand_model.get_atoms():
    ligand_i_seqs.append(atom.tmp)
  hd_selection = electron_model.get_hd_selection()
  ligand_selection = []
  for i, (sel, atom) in enumerate(zip(hd_selection, electron_model.get_atoms())):
    if atom.tmp in ligand_i_seqs:
      ligand_selection.append(True)
    else:
      ligand_selection.append(False)
  if qmr.include_nearest_neighbours_in_optimisation:
    for i, (sel, atom) in enumerate(zip(ligand_selection, electron_model.get_atoms())):
      if atom.name.strip() in ['CA', 'C', 'N', 'O', 'OXT']: continue
      ligand_selection[i]=True
  if 'main_chain_to_delta' in qmr.protein_optimisation_freeze:
    for i, (sel, atom) in enumerate(zip(ligand_selection, electron_model.get_atoms())):
      if atom.name.strip() in ['CA', 'C', 'N', 'O', 'OXT', 'CB', 'CG']: # mostly for HIS...
        ligand_selection[i]=False
  elif 'main_chain_to_beta' in qmr.protein_optimisation_freeze:
    for i, (sel, atom) in enumerate(zip(ligand_selection, electron_model.get_atoms())):
      if atom.name.strip() in ['CA', 'C', 'N', 'O', 'OXT', 'CB']:
        ligand_selection[i]=False
  elif 'main_chain' in qmr.protein_optimisation_freeze:
    for i, (sel, atom) in enumerate(zip(ligand_selection, electron_model.get_atoms())):
      if atom.name.strip() in ['CA', 'C', 'N', 'O', 'OXT']:
        ligand_selection[i]=False
  if qmr.freeze_specific_atoms:
    min_d2=1e9
    min_i=None
    ph=ligand_model.get_hierarchy()
    atoms = ph.atoms()
    xyzs=atoms.extract_xyz()
    m=xyzs.mean()
    for i, (sel, atom) in enumerate(zip(ligand_selection, electron_model.get_atoms())):
      if sel and not atom.element_is_hydrogen():
        d2 = dist2(m, atom.xyz)
        if d2<min_d2:
          min_d2=d2
          min_i=i
    ligand_selection[min_i]=False
  qmm.set_ligand_atoms(ligand_selection)
  return qmm

def qm_restraints_initialisation(params, log=StringIO()):
  for i, qmr in enumerate(params.qi.qm_restraints):
    if not i: print('  QM restraints selections', file=log)
    print('    %s - buffer %s (%s)' % (qmr.selection,
                                       qmr.buffer,
                                       qmr.capping_groups), file=log)
  print('',file=log)
  quantum_interface.get_qi_macro_cycle_array(params, verbose=True, log=log)

def running_this_macro_cycle(qmr,
                             macro_cycle,
                             number_of_macro_cycles=-1,
                             energy_only=False,
                             pre_refinement=True,
                             verbose=False,
                             ):
  from mmtbx.geometry_restraints.quantum_interface import get_qi_macro_cycle_array
  if not energy_only:
    if 'in_situ_opt' not in qmr.calculate: return False
    if qmr.run_in_macro_cycles=='all':
      return 'restraints'
    elif qmr.run_in_macro_cycles in ['first_only', 'first_and_last'] and macro_cycle==1:
      return 'restraints'
    elif ( qmr.run_in_macro_cycles in ['first_and_last', 'last_only'] and
          macro_cycle==number_of_macro_cycles):
      return 'restraints'
    elif qmr.run_in_macro_cycles=='test' and macro_cycle in [0, None]:
      return 'restraints'
  else:
    if pre_refinement:
      checks = 'starting_strain starting_energy starting_bound'
      tmp = set(checks.split())
      inter = tmp.intersection(set(qmr.calculate))
      if macro_cycle==1:
        return list(inter)
    else:
      checks = 'final_strain final_energy final_bound'
      tmp = set(checks.split())
      inter = tmp.intersection(set(qmr.calculate))
      if macro_cycle==number_of_macro_cycles or macro_cycle==-1:
        return list(inter)
  return False

def update_bond_restraints(ligand_model,
                           buffer_model,
                           model_grm=None, # flag for update vs checking
                           ignore_x_h_distance_protein=False,
                           include_inter_residue_restraints=False,
                           log=StringIO()):
  ligand_grm = ligand_model.get_restraints_manager()
  ligand_atoms = ligand_model.get_atoms()
  ligand_i_seqs = []
  for atom in ligand_atoms: ligand_i_seqs.append(atom.tmp)
  buffer_grm = buffer_model.get_restraints_manager()
  atoms = buffer_model.get_atoms()
  bond_proxies_simple, asu = buffer_grm.geometry.get_all_bond_proxies(
    sites_cart=buffer_model.get_sites_cart())
  sorted_table, n_not_shown = bond_proxies_simple.get_sorted(
    'delta',
    buffer_model.get_sites_cart())
  i=0
  for info in sorted_table:
    #
    # loop over buffer restraints
    #
    (i_seq, j_seq, i_seqs, distance_ideal, distance_model, slack, delta, sigma, weight, residual, sym_op_j, rt_mx) = info
    i_atom=atoms[i_seq]
    j_atom=atoms[j_seq]
    if model_grm:
      if i_atom.element_is_hydrogen(): continue
      if j_atom.element_is_hydrogen(): continue
    i_seqs=[i_seq, j_seq]
    bond=buffer_grm.geometry.bond_params_table.lookup(*list(i_seqs))
    i+=1
    if model_grm:
      if include_inter_residue_restraints:
        if not(i_atom.tmp in ligand_i_seqs or j_atom.tmp in ligand_i_seqs):
          continue
      else:
        if not(i_atom.tmp in ligand_i_seqs and j_atom.tmp in ligand_i_seqs):
          continue
      print('    %-2d %s - %s %5.3f ~> %5.3f' % (
        i,
        i_atom.id_str().replace('pdb=',''),
        j_atom.id_str().replace('pdb=',''),
        bond.distance_ideal,
        distance_model), file=log)
      bond.distance_ideal=distance_model
      i_seqs=[i_atom.tmp, j_atom.tmp]
      bond=model_grm.geometry.bond_params_table.lookup(*list(i_seqs))
      bond.distance_ideal=distance_model
    else:
      if ( i_atom.element_is_hydrogen() or j_atom.element_is_hydrogen()):
        if distance_model>1.5:
          print('    %-2d %s - %s %5.3f ~> %5.3f' % (
            i,
            i_atom.id_str().replace('pdb=',''),
            j_atom.id_str().replace('pdb=',''),
            bond.distance_ideal,
            distance_model), file=log)
          if not ignore_x_h_distance_protein:
            raise Sorry('''
  The QM optimisation has caused a X-H covalent bond to exceed 1.5 Angstrom.
  This may be because the input geometry was not appropriate or the QM method
  is not providing the biological answer. Check the QM result for issues. This
  check can be skipped by using ignore_x_h_distance_protein.
  ''')

def update_bond_restraints_simple(model):
  """Update bond restraints in model to match the actual model values

  Args:
      model (model): model!
  """
  grm = model.get_restraints_manager()
  atoms = model.get_atoms()
  bond_proxies_simple, asu = grm.geometry.get_all_bond_proxies(
    sites_cart=model.get_sites_cart())
  sorted_table, n_not_shown = bond_proxies_simple.get_sorted(
    'delta',
    model.get_sites_cart())
  # for single ions there is no bond table
  if sorted_table is None: return
  for info in sorted_table:
    (i_seq, j_seq, i_seqs, distance_ideal, distance_model, slack, delta, sigma, weight, residual, sym_op_j, rt_mx) = info
    i_atom=atoms[i_seq]
    j_atom=atoms[j_seq]
    # exclude X-H because x-ray...
    if i_atom.element_is_hydrogen(): continue
    if j_atom.element_is_hydrogen(): continue
    i_seqs=[i_seq, j_seq]
    bond=grm.geometry.bond_params_table.lookup(*list(i_seqs))
    bond.distance_ideal=distance_model

def update_angle_restraints(ligand_model,
                            buffer_model,
                            model_grm=None, # flag for update vs checking
                            ignore_x_h_distance_protein=False,
                            include_inter_residue_restraints=False,
                            log=StringIO()):
  ligand_grm = ligand_model.get_restraints_manager()
  ligand_atoms = ligand_model.get_atoms()
  ligand_i_seqs = []
  for atom in ligand_atoms: ligand_i_seqs.append(atom.tmp)
  buffer_grm = buffer_model.get_restraints_manager()
  atoms = buffer_model.get_atoms()
  # ligand_i_seq_min=None
  # for atom in atoms:
  #   if atom.tmp in ligand_i_seqs:
  #     ligand_i_seq_min=atom.i_seq
  #     break
  sorted_table, n_not_shown = buffer_grm.geometry.angle_proxies.get_sorted(
    'delta',
    buffer_model.get_sites_cart())
  # ligand_lookup = {}
  # model_lookup = {}
  i=0
  if sorted_table is None: sorted_table=[]
  for info in sorted_table:
    (i_seqs, angle_ideal, angle_model, delta, sigma, weight, residual) = info
    i_atom=atoms[int(i_seqs[0])]
    j_atom=atoms[int(i_seqs[1])]
    k_atom=atoms[int(i_seqs[2])]
    key = [i_atom.tmp, j_atom.tmp, k_atom.tmp]
    intersect = set(ligand_i_seqs).intersection(set(key))
    if include_inter_residue_restraints:
      if not len(intersect): continue
    else:
      if len(intersect)!=3: continue
    # key = (int(i_seqs[0])-ligand_i_seq_min,
    #        int(i_seqs[1])-ligand_i_seq_min,
    #        int(i_seqs[2])-ligand_i_seq_min)
    # key = (int(i_seqs[0]), int(i_seqs[1]), int(i_seqs[2]))
    # ligand_lookup[key]=angle_model
    # key = (int(i_seqs[0]), int(i_seqs[1]), int(i_seqs[2]))
    i+=1
    print('    %-2d %s - %s - %s %5.1f ~> %5.1f' % (
      i,
      i_atom.id_str().replace('pdb=',''),
      j_atom.id_str().replace('pdb=',''),
      k_atom.id_str().replace('pdb=',''),
      angle_ideal,
      angle_model), file=log)
    assert len(intersect)!=0, '%s' % intersect
    # key = (atoms[key[0]].tmp, atoms[key[1]].tmp, atoms[key[2]].tmp)
    # model_lookup[key]=angle_model
    # # key = (int(i_seqs[2])-ligand_i_seq_min,
    #        int(i_seqs[1])-ligand_i_seq_min,
    #        int(i_seqs[0])-ligand_i_seq_min)
    # ligand_lookup[key]=angle_model
    # key = (atoms[key[2]].tmp, atoms[key[1]].tmp, atoms[key[0]].tmp)
    # model_lookup[key]=angle_model
  # for angle_proxy in ligand_grm.geometry.angle_proxies:
  #   angle = ligand_lookup.get(angle_proxy.i_seqs, None)
  #   print('angle',angle_proxy.i_seqs, angle)
  #   tmp=ligand_model.get_atoms()
  #   print(atoms[angle_proxy.i_seqs[0]].quote())
  #   print(atoms[angle_proxy.i_seqs[1]].quote())
  #   print(atoms[angle_proxy.i_seqs[2]].quote())
  #   if angle is None: continue
  #   angle_proxy.angle_ideal=angle
  # for angle_proxy in model_grm.geometry.angle_proxies:
  #   angle = model_lookup.get(angle_proxy.i_seqs, None)
  #   if angle is None: continue
  #   angle_proxy.angle_ideal=angle

  # assert 0

def update_angle_restraints_simple(model):
  """Update angle restraints in model to match the actual model values

  Args:
      model (model): model!
  """
  grm = model.get_restraints_manager()
  atoms = model.get_atoms()
  sorted_table, n_not_shown = grm.geometry.angle_proxies.get_sorted(
    'delta',
    model.get_sites_cart())
  if sorted_table is None: return
  lookup={}
  for info in sorted_table:
    (i_seqs, angle_ideal, angle_model, delta, sigma, weight, residual) = info
    for i in range(len(i_seqs)):
      i_seqs[i]=int(i_seqs[i])
    lookup[tuple(i_seqs)]=angle_model
  for angle_proxy in grm.geometry.angle_proxies:
    angle = lookup.get(angle_proxy.i_seqs, None)
    # tmp=model.get_atoms()
    # print(atoms[angle_proxy.i_seqs[0]].quote())
    # print(atoms[angle_proxy.i_seqs[1]].quote())
    # print(atoms[angle_proxy.i_seqs[2]].quote())
    if angle is None: assert 0
    angle_proxy.angle_ideal=angle

def update_dihedral_restraints( ligand_model,
                                buffer_model,
                                model_grm=None, # flag for update vs checking
                                ignore_x_h_distance_protein=False,
                                include_inter_residue_restraints=False,
                                log=StringIO()):
  ligand_grm = ligand_model.get_restraints_manager()
  ligand_atoms = ligand_model.get_atoms()
  ligand_i_seqs = []
  for atom in ligand_atoms: ligand_i_seqs.append(atom.tmp)
  buffer_grm = buffer_model.get_restraints_manager()
  atoms = buffer_model.get_atoms()
  # ligand_i_seq_min=None
  # for atom in atoms:
  #   if atom.tmp in ligand_i_seqs:
  #     ligand_i_seq_min=atom.i_seq
  #     break
  sorted_table, n_not_shown = buffer_grm.geometry.dihedral_proxies.get_sorted(
    'delta',
    buffer_model.get_sites_cart())
  # ligand_lookup = {}
  # model_lookup = {}
  i=0
  if sorted_table is None: sorted_table=[]
  for info in sorted_table:
    (i_seqs, angle_ideal, angle_model, delta, period, sigma, weight, residual) = info
    i_atom=atoms[int(i_seqs[0])]
    j_atom=atoms[int(i_seqs[1])]
    k_atom=atoms[int(i_seqs[2])]
    l_atom=atoms[int(i_seqs[3])]
    key = [i_atom.tmp, j_atom.tmp, k_atom.tmp, l_atom.tmp]
    intersect = set(ligand_i_seqs).intersection(set(key))
    if include_inter_residue_restraints:
      if not len(intersect): continue
    else:
      if len(intersect)!=4: continue
    i+=1
    print('    %-2d %s - %s - %s - %s %5.1f ~> %5.1f' % (
      i,
      i_atom.id_str().replace('pdb=',''),
      j_atom.id_str().replace('pdb=',''),
      k_atom.id_str().replace('pdb=',''),
      l_atom.id_str().replace('pdb=',''),
      angle_ideal,
      angle_model), file=log)
    assert len(intersect)!=0, '%s' % intersect

def update_dihedral_restraints_simple(model):
  """Update dihedral restraints in model to match the actual model values

  Args:
      model (model): model!
  """
  grm = model.get_restraints_manager()
  atoms = model.get_atoms()
  sorted_table, n_not_shown = grm.geometry.dihedral_proxies.get_sorted(
    'delta',
    model.get_sites_cart())
  if sorted_table is None: return
  lookup={}
  for info in sorted_table:
    (i_seqs, angle_ideal, angle_model, delta, period, sigma, weight, residual) = info
    for i in range(len(i_seqs)):
      i_seqs[i]=int(i_seqs[i])
    lookup[tuple(i_seqs)]=angle_model
  for angle_proxy in grm.geometry.dihedral_proxies:
    angle = lookup.get(angle_proxy.i_seqs, None)
    if angle is None: assert 0
    angle_proxy.angle_ideal=angle

def get_program_goal(qmr, macro_cycle=None, energy_only=False):
  program_goal=[] # can be 'opt', 'energy', 'strain'
  if not energy_only:
    program_goal=['opt']
    return program_goal
  if macro_cycle==1:
    if qmr.calculate.count('starting_energy'):
      program_goal.append('energy')
    if qmr.calculate.count('starting_strain'):
      program_goal.append('strain')
    if qmr.calculate.count('starting_bound'):
      program_goal.append('bound')
  else: # only called with final energy on final macro cycle
    if qmr.calculate.count('final_energy'):
      program_goal.append('energy')
    if qmr.calculate.count('final_strain'):
      program_goal.append('strain')
    if qmr.calculate.count('final_bound'):
      program_goal.append('bound')
  return program_goal

def setup_qm_jobs(model,
                  params,
                  macro_cycle,
                  energy_only=False,
                  pre_refinement=True,
                  log=StringIO()):
  prefix = get_prefix(params)
  objects = []
  # if params.qi.working_directory:
  #   if params.qi.working_directory is Auto:
  #     working_directory = prefix
  #   else:
  #     working_directory = params.qi.working_directory
  #   if not os.path.exists(working_directory):
  #     os.mkdir(working_directory)
  #   print('  Changing to %s' % working_directory, file=log)
  #   os.chdir(working_directory)
  for i, qmr in enumerate(params.qi.qm_restraints):
    if len(qmr.freeze_specific_atoms)>2:
      raise Sorry('Only Auto supported so multiple freezes not necessary.')
    elif len(qmr.freeze_specific_atoms)==1:
      if qmr.freeze_specific_atoms[0].atom_selection!=Auto:
        raise Sorry('Freezing ligand atoms only supports "Auto" for centre of mass.')
    number_of_macro_cycles = 1
    if hasattr(params, 'main'):
      number_of_macro_cycles = params.main.number_of_macro_cycles
    if macro_cycle is not None and not running_this_macro_cycle(
        qmr,
        macro_cycle,
        energy_only=energy_only,
        number_of_macro_cycles=number_of_macro_cycles,
        pre_refinement=pre_refinement):
      # print('    Skipping this selection in this macro_cycle : %s' % qmr.selection,
      #       file=log)
      continue
    #
    # get ligand and buffer region models
    #
    ligand_model, buffer_model = get_ligand_buffer_models(model, qmr)
    assert buffer_model.restraints_manager_available()
    #
    # get appropriate QM manager
    #
    program_goals = get_program_goal(qmr, macro_cycle, energy_only=energy_only)
    for program_goal in program_goals:
      qmm = get_qm_manager(ligand_model, buffer_model, qmr, program_goal, log=log)
      preamble = quantum_interface.get_preamble(macro_cycle, i, qmr)
      if not energy_only: # only write PDB files for restraints update
        if 'pdb_core' in qmr.write_files:
          write_pdb_file(ligand_model, '%s_ligand_%s.pdb' % (prefix, preamble), log)
        if 'pdb_buffer' in qmr.write_files:
          write_pdb_file(buffer_model, '%s_cluster_%s.pdb' % (prefix, preamble), log)
      qmm.preamble='%s_%s' % (prefix, preamble)
      # for attr in ['exclude_torsions_from_optimisation']:
      #   setattr(qmm, attr, getattr(qmr, attr))
      attr = 'exclude_torsions_from_optimisation'
      setattr(qmm, attr, qmr.protein_optimisation_freeze.count('torsions'))
      #
      objects.append([ligand_model, buffer_model, qmm, qmr])
  print('',file=log)
  return objects

def run_jobs(objects, macro_cycle, nproc=1, log=StringIO()):
  assert objects
  from mmtbx.geometry_restraints.qi_utils import run_serial_or_parallel
  argstuples=[]
  for i, (ligand_model, buffer_model, qmm, qmr) in enumerate(objects):
    argstuples.append((qmm,
                       qmr.cleanup,
                       qmr.package.read_output_to_skip_opt_if_available,
                       not(qmr.package.ignore_input_differences),
                       log,
                       ))
  results = run_serial_or_parallel(qm_manager.qm_runner, argstuples, nproc)
  if results:
    xyzs = []
    xyzs_buffer = []
    energies = {}
    for i, (ligand_model, buffer_model, qmm, qmr) in enumerate(objects):
      xyz, xyz_buffer = results[i]
      units=''
      if qmm.program_goal in ['opt']:
        energy, units = qmm.read_energy()
      elif qmm.program_goal in ['energy', 'strain', 'bound']:
        energy=xyz
        units=xyz_buffer
        xyz=None
        xyz_buffer=None
      else:
        assert 0, 'program_goal %s not in list' % qmm.program_goal
      energies.setdefault(qmr.selection,[])
      energies[qmr.selection].append([qmm.program_goal,
                                      energy,
                                      ligand_model.get_number_of_atoms(),
                                      buffer_model.get_number_of_atoms()
                                      ])
      xyzs.append(xyz)
      xyzs_buffer.append(xyz_buffer)
      print('  Time for calculation of "%s" using %s %s %s: %s' % (
        qmr.selection,
        qmr.package.method,
        qmr.package.basis_set,
        qmr.package.solvent_model,
        qmm.get_timings().split(':')[-1],
        ), file=log)
  print('',file=log)
  return xyzs, xyzs_buffer, energies, units

def run_energies(model,
                 params,
                 macro_cycle=None,
                 run_program=True,
                 pre_refinement=True,
                 nproc=1,
                 log=StringIO(),
                 ):
  t0 = time.time()
  energy_only=True
  if not model.restraints_manager_available():
    model.log=null_out()
    model.process(make_restraints=True)
  if macro_cycle in [None, 0]: run_program=False
  # qi_array = quantum_interface.get_qi_macro_cycle_array(params)
  if quantum_interface.is_quantum_interface_active_this_macro_cycle(params,
                                                                    macro_cycle,
                                                                    energy_only=energy_only,
                                                                    # pre_refinement=pre_refinement,
                                                                    ) and run_program:
    print('  QM energy calculations for macro cycle %s' % macro_cycle, file=log)
  #
  # setup QM jobs
  #
  objects = setup_qm_jobs(model,
                          params,
                          macro_cycle,
                          energy_only=energy_only,
                          pre_refinement=pre_refinement,
                          log=log)
  if not run_program: return
  assert macro_cycle is not None
  #
  # run jobs
  #
  xyzs, xyzs_buffer, energies, units = run_jobs(objects,
                                                macro_cycle=macro_cycle,
                                                nproc=nproc,
                                                log=log)
  print('  Total time for QM energies: %0.1fs' % (time.time()-t0), file=log)
  print('%s%s' % ('<'*40, '>'*40), file=log)
  return group_args(energies=energies,
                    units=units,
                    # rmsds=rmsds,
                    # times=times,
                    )

def update_restraints(model,
                      params,
                      macro_cycle=None,
                      # run_program=True,
                      # transfer_internal_coordinates=True,
                      never_write_restraints=False,
                      nproc=1,
                      parallel_id=None,
                      log=StringIO(),
                      ):
  def is_ligand_going_to_be_same_size(qmr):
    rc=True
    inter = set(qmr.protein_optimisation_freeze).intersection(set(['main_chain_to_delta',
                                                                  'main_chain_to_beta',
                                                                  'main_chain',
                                                                  'torsions']))
    if (qmr.include_nearest_neighbours_in_optimisation or inter):
      rc=False
    if len(qmr.freeze_specific_atoms)>0: rc=False
    return rc
  t0 = time.time()
  times=[]
  energy_only=False
  if not model.restraints_manager_available():
    model.log=null_out()
    model.process(make_restraints=True)
  if quantum_interface.is_quantum_interface_active_this_macro_cycle(params,
                                                                    macro_cycle,
                                                                    energy_only=energy_only,
                                                                    ):
    print('  QM restraints calculations for macro cycle %s' % macro_cycle,
      file=log)
  #
  # setup QM jobs
  #
  objects = setup_qm_jobs(model, params, macro_cycle, energy_only=energy_only, log=log)
  #
  # run jobs
  #
  assert objects
  if not objects: return None
  xyzs, xyzs_buffer, energies, units = run_jobs(objects,
                                                macro_cycle=macro_cycle,
                                                nproc=nproc,
                                                log=log)
  times.append(time.time()-t0)
  #
  # update model restraints
  #
  rmsds=[]
  final_pdbs = []
  prefix = get_prefix(params)
  for i, ((ligand_model, buffer_model, qmm, qmr), xyz, xyz_buffer) in enumerate(
    zip(objects,
        xyzs,
        xyzs_buffer,
        )):
    final_pdbs.append([])
    if qmr.package.view_output: qmm.view(qmr.package.view_output)
    if i: print(' ',file=log)
    print('  Updating QM restraints: "%s"' % qmr.selection, file=log)
    print(show_ligand_buffer_models(ligand_model, buffer_model), file=log)
    gs = ligand_model.geometry_statistics()
    print('  Starting stats: %s' % gs.show_bond_and_angle_and_dihedral(), file=log)
    #
    # update coordinates of ligand
    #
    ligand_rmsd = None
    old = ligand_model.get_hierarchy().atoms().extract_xyz()
    if is_ligand_going_to_be_same_size(qmr):
      ligand_rmsd = old.rms_difference(xyz)
      if ligand_rmsd>5:
        print('  QM minimisation has large rms difference in cartesian coordinates: %0.1f' % (ligand_rmsd),
              file=log)
        print('  Check the QM minimisation for errors or incorrect protonation.',
              file=log)
        if ligand_rmsd>20:
          print('  Movement of cartesian coordinates is very large.', file=log)
      ligand_model.get_hierarchy().atoms().set_xyz(xyz)
    old = buffer_model.get_hierarchy().atoms().extract_xyz()
    # rmsd = old.rms_difference(xyz_buffer)
    buffer_model.get_hierarchy().atoms().set_xyz(xyz_buffer)
    #
    ligand_atoms = ligand_model.get_hierarchy().atoms()
    ligand_i_seqs = []
    for atom in ligand_atoms:
      if atom.element.strip() in ['H', 'D']: continue
      ligand_i_seqs.append(atom.id_str())
    buffer_atoms = buffer_model.get_hierarchy().atoms()
    new_old = flex.vec3_double()
    new_new = flex.vec3_double()
    for atom, told, tnew in zip(buffer_atoms,old,xyz_buffer):
      if atom.id_str() in ligand_i_seqs:
        new_old.append(told)
        new_new.append(tnew)
    rmsd = new_old.rms_difference(new_new)
    rmsds.append([ligand_rmsd, rmsd])
    print('    RMS difference in entire QM model : %9.3f' % (rmsd), file=log)
    #
    gs = ligand_model.geometry_statistics()
    print('  Interim stats : %s' % gs.show_bond_and_angle_and_dihedral(), file=log)
    preamble = quantum_interface.get_preamble(macro_cycle, i, qmr)
    if 'pdb_final_core' in qmr.write_files:
      write_pdb_file(ligand_model, '%s_ligand_final_%s.pdb' % (prefix, preamble), log)
      final_pdbs[-1].append('%s_ligand_final_%s.pdb' % (prefix, preamble))
    if 'pdb_final_buffer' in qmr.write_files:
      write_pdb_file(buffer_model, '%s_cluster_final_%s.pdb' % (prefix, preamble), log)
      final_pdbs[-1].append('%s_cluster_final_%s.pdb' % (prefix, preamble))
    if qmr.do_not_update_restraints:
      print('  Skipping updating restaints')
      continue
    #
    # transfer geometry to proxies
    #  - bonds
    #
    model_grm = model.get_restraints_manager()
    print('\n  Checking', file=log)
    update_bond_restraints(buffer_model,
                           buffer_model,
                           ignore_x_h_distance_protein=qmr.ignore_x_h_distance_protein,
                           log=log)
    print('\n  Transfer', file=log)
    update_bond_restraints(ligand_model,
                           buffer_model,
                           model_grm=model_grm,
                           include_inter_residue_restraints=qmr.include_inter_residue_restraints,
                           log=log)
    update_bond_restraints_simple(ligand_model)
    #
    #  - angles
    #
    update_angle_restraints(ligand_model,
                            buffer_model,
                            model_grm=model_grm,
                            include_inter_residue_restraints=qmr.include_inter_residue_restraints,
                            log=log)
    update_angle_restraints_simple(ligand_model)
    #
    #  - torsions
    #
    update_dihedral_restraints( ligand_model,
                                buffer_model,
                                model_grm=model_grm,
                                include_inter_residue_restraints=qmr.include_inter_residue_restraints,
                                log=log)
    update_dihedral_restraints_simple(ligand_model)
    print('', file=log)
    #
    # final stats
    #
    gs = ligand_model.geometry_statistics()
    print('  Finished stats : %s' % gs.show_bond_and_angle_and_dihedral(
            assert_zero=not qmr.include_inter_residue_restraints),
          file=log)
    print('%s%s' % (' '*19, gs.show_planarity_details()), file=log)
    r=gs.result()
    if r.planarity.mean>0.02 or r.planarity.max>0.05:
      print('  %s\n   rmsd values for planarity restraints are high. Check QM minimisation. \n  %s' % (
            '-'*71,
            '-'*71,
            ),
            file=log)
    if 'restraints' in qmr.write_files and not never_write_restraints:
      header='''
Restraints written by QMR process in phenix.refine
      ''' % ()
      if qmr.restraints_filename is not Auto:
        tmp_cif_filename = qmr.restraints_filename
      else:
        tmp_cif_filename = '%s.cif' % qmm.preamble
      if not tmp_cif_filename.endswith('.cif'):
        tmp_cif_filename = '%s.cif' % tmp_cif_filename
      write_restraints(ligand_model,
                       tmp_cif_filename,
                       header=header,
                       log=log,
                       )
  print('\n  Total time for QM restaints: %0.1fs\n' % (time.time()-t0), file=log)
  print('%s%s' % ('/'*39, '\\'*40), file=log)
  print('%s%s' % ('\\'*39, '/'*40), file=log)
  return group_args(energies=energies,
                    units=units,
                    rmsds=rmsds,
                    times=times,
                    final_pdbs=final_pdbs,
                    )

if __name__ == '__main__':
  print(quantum_chemistry_scope)
