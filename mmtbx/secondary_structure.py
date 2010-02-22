
import iotbx.pdb.secondary_structure
from scitbx.array_family import shared, flex
import libtbx.phil
import libtbx.object_oriented_patterns as oop
from libtbx import smart_open, easy_run
from libtbx.utils import Sorry, Usage
from libtbx import adopt_init_args, group_args
from math import sqrt
import cStringIO
import sys, os

default_sigma = 0.05
default_slack = 0.00

ss_restraint_params_str = """
  verbose = False
    .type = bool
  substitute_n_for_h = None
    .type = bool
    .style = tribool
  restrain_helices = True
    .type = bool
  alpha_only = False
    .type = bool
  restrain_sheets = True
    .type = bool
  remove_outliers = True
    .type = bool
  restrain_initial_values = False
    .type = bool
  sigma = %.3f
    .type = float
  slack = %.3f
    .type = float
  n_o_distance_ideal = 3.0
    .type = float
  n_o_outlier_max_delta = 0.5
    .type = float
  h_o_distance_ideal = 2.0
    .type = float
  h_o_outlier_max_delta = 0.5
    .type = float
""" % (default_sigma, default_slack)

ss_tardy_params_str = """\
tardy
  .help = UNUSED
  .style = box auto_align noauto
{
  group_helix_backbone = False
    .style = bool
}
"""

helix_classes = ["unknown"] * 10
helix_classes[0] = "alpha"
helix_classes[2] = "pi"
helix_classes[4] = "3_10"

def get_helix_class (helix_class) :
  class_id = int(helix_class) - 1
  return helix_classes[class_id]

ss_group_params_str = """
helix
  .multiple = True
  .optional = True
{
  selection = None
    .type = str
    .style = bold selection
  helix_class = *1 2 3 4 5 6 7 8 9 10
    .type = choice
    .caption = alpha other pi other 3_10 other other other other other
    .help = Type of helix, defaults to alpha (1).  Only alpha, pi, and 3_10 \
      helices are used for hydrogen-bond restraints.
    .style = bold
  restraint_sigma = None
    .type = float
  restraint_slack = None
    .type = float
  backbone_only = False
    .type = bool
    .help = Only applies to rigid-body groupings, and not H-bond restraints \
      which are already backbone-only.
}
sheet
  .multiple = True
  .optional = True
{
  first_strand = None
    .type = str
    .style = bold selection
  strand
    .multiple = True
    .optional = True
  {
    selection = None
      .type = str
      .style = bold selection
    sense = parallel antiparallel *unknown
      .type = choice
      .style = bold
    bond_start_current = None
      .type = str
      .style = bold selection
    bond_start_previous = None
      .type = str
      .style = bold selection
  }
  restraint_sigma = None
    .type = float
  restraint_slack = None
    .type = float
  backbone_only = False
    .type = bool
    .help = Only applies to rigid-body groupings, and not H-bond restraints \
      which are already backbone-only.
}
"""

ss_tardy_params_str = "" # XXX: remove this later

sec_str_master_phil_str = """
input
  .style = box auto_align
{
%s
  find_automatically = None
    .type = bool
    .style = bold tribool
}
h_bond_restraints
  .short_caption = Hydrogen bonding restraints
  .style = box auto_align
{
%s
}
%s
%s
""" % (iotbx.pdb.secondary_structure.ss_input_params_str,
       ss_restraint_params_str, ss_tardy_params_str, ss_group_params_str)

sec_str_master_phil = libtbx.phil.parse(sec_str_master_phil_str)
default_params = sec_str_master_phil.extract()

use_resids = False # XXX: for debugging purposes only

class _annotation (oop.injector, iotbx.pdb.secondary_structure.annotation) :
  def as_restraint_groups (self, log=sys.stderr, prefix_scope="") :
    phil_strs = []
    for helix in self.helices :
      helix_phil = helix.as_restraint_group(log, prefix_scope)
      if helix_phil is not None :
        phil_strs.append(helix_phil)
    for sheet in self.sheets :
      sheet_phil = sheet.as_restraint_group(log, prefix_scope)
      if sheet_phil is not None :
        phil_strs.append(sheet_phil)
    return "\n".join(phil_strs)

class _pdb_helix (oop.injector, iotbx.pdb.secondary_structure.pdb_helix) :
  def as_restraint_group (self, log=sys.stderr, prefix_scope="") :
    if self.start_chain_id != self.end_chain_id :
      print >> log, "Helix chain ID mismatch: starts in %s, ends in %s" % (
        self.start_chain_id, self.end_chain_id)
      return None
    if use_resids :
      resid_start = "%d%s" % (self.start_resseq, self.start_icode)
      resid_end = "%d%s" % (self.end_resseq, self.end_icode)
      sele = "chain '%s' and resid %s through %s" % (self.start_chain_id,
        resid_start, resid_end)
    else :
      sele = "chain '%s' and resseq %d:%d" % (self.start_chain_id,
        self.start_resseq, self.end_resseq)
    if prefix_scope != "" and not prefix_scope.endswith(".") :
      prefix_scope += "."
    rg = """\
%shelix {
  selection = "%s"
  helix_class = %d
}""" % (prefix_scope, sele, self.helix_class)
    return rg

class _pdb_sheet (oop.injector, iotbx.pdb.secondary_structure.pdb_sheet) :
  def as_restraint_group (self, log=sys.stderr, prefix_scope="") :
    if len(self.strands) == 0 :
      return None
    selections = []
    senses = []
    reg_curr = []
    reg_prev = []
    for (strand,registration) in zip(self.strands, self.registrations) :
      if use_resids :
        resid_start = "%d%s" % (strand.start_resseq, strand.start_icode)
        resid_end = "%d%s" % (strand.end_resseq, strand.end_icode)
        sele = "chain '%s' and resid %s through %s" % (strand.start_chain_id,
          resid_start, resid_end)
      else :
        sele = "chain '%s' and resseq %d:%d" % (strand.start_chain_id,
          strand.start_resseq, strand.end_resseq)
      selections.append(sele)
      if strand.sense == 0 :
        senses.append("unknown")
      elif strand.sense == -1 :
        senses.append("antiparallel")
      elif strand.sense == 1 :
        senses.append("parallel")
      else :
        raise Sorry("Sense must be 0, 1, or -1.")
      if registration is not None :
        if use_resids :
          sele_base = "chain '%s' and resid %s"
          resid_curr = "%d%s" % (registration.cur_resseq,registration.cur_icode)
          resid_prev = "%d%s" % (registration.prev_resseq,registration.prev_icode)
          reg_curr.append(sele_base % (registration.cur_chain_id,resid_curr))
          reg_prev.append(sele_base % (registration.prev_chain_id,resid_prev))
        else :
          reg_curr.append("chain '%s' and resseq %d" % (
            registration.cur_chain_id, registration.cur_resseq))
          reg_prev.append("chain '%s' and resseq %d" % (
            registration.prev_chain_id, registration.prev_resseq))
      else :
        reg_curr.append(None)
        reg_prev.append(None)
    n = 0
    first_strand = None
    strands = []
    for (sele, sense, curr, prev) in zip(selections,senses,reg_curr,reg_prev) :
      if n == 0 :
        first_strand = sele
      else :
        strands.append("""\
  strand {
    selection = "%s"
    sense = %s
    bond_start_current = "%s"
    bond_start_previous = "%s"
  }""" % (sele, sense, curr, prev))
      n += 1
    assert first_strand is not None
    if prefix_scope != "" and not prefix_scope.endswith(".") :
      prefix_scope += "."
    phil_str = """
%ssheet {
  first_strand = "%s"
%s
}""" % (prefix_scope, first_strand, "\n".join(strands))
    return phil_str

class hydrogen_bond_table (object) :
  def __init__ (self, bonds, distance, sigma, slack, bond_lengths) :
    assert (bonds.size() == distance.size() == sigma.size() == slack.size() ==
      bond_lengths.size())
    adopt_init_args(self, locals())
    self.flag_use_bond = flex.bool(bonds.size(), True)

  def analyze_distances (self, params, pdb_hierarchy=None, log=sys.stderr) :
    atoms = None
    if params.verbose :
      assert pdb_hierarchy is not None
      atoms = pdb_hierarchy.atoms()
    remove_outliers = params.remove_outliers
    delta_max = params.h_o_outlier_max_delta
    distance_ideal = params.h_o_distance_ideal
    if params.substitute_n_for_h :
      delta_max = params.n_o_outlier_max_delta
      distance_ideal = params.n_o_distance_ideal
    atoms = pdb_hierarchy.atoms()
    hist =  flex.histogram(self.bond_lengths, 10)
    print >> log, "  Distribution of hydrogen bond lengths without filtering:"
    hist.show(f=log, prefix="    ", format_cutoffs="%.4f")
    print >> log, ""
    if not remove_outliers :
      return False
    for i, distance in enumerate(self.bond_lengths) :
      if abs(distance - distance_ideal) > delta_max :
        self.flag_use_bond[i] = False
        if params.verbose :
          print >> log, "Excluding H-bond with length %.3fA" % distance
          i_seq, j_seq = self.bonds[i]
          print >> log, "  %s" % atoms[i_seq].fetch_labels().id_str()
          print >> log, "  %s" % atoms[j_seq].fetch_labels().id_str()
    print >> log, "  After filtering: %d bonds remaining." % \
      self.flag_use_bond.count(True)
    print >> log, "  Distribution of hydrogen bond lengths after applying cutoff:"
    hist = flex.histogram(self.bond_lengths.select(self.flag_use_bond), 10)
    hist.show(f=log, prefix="    ", format_cutoffs="%.4f")
    print >> log, ""
    return True

  def get_bond_restraint_data (self, filter=True) :
    for i, (donor_i_seq, acceptor_i_seq) in enumerate(self.bonds) :
      if not filter or self.flag_use_bond[i] :
        yield group_args(donor_i_seq=donor_i_seq,
          acceptor_i_seq=acceptor_i_seq,
          sigma=self.sigma[i],
          slack=self.slack[i],
          distance_ideal=self.distance[i])

  def get_simple_bonds (self, filter=True) :
    if filter :
      for i, bond in enumerate(self.bonds) :
        if self.flag_use_bond[i] :
          yield bond
    else :
      for i, bond in enumerate(self.bonds) :
        yield bond

  def as_pymol_dashes (self, pdb_hierarchy, filter=True, out=sys.stdout) :
    atoms = pdb_hierarchy.atoms()
    for (i_seq, j_seq) in self.get_simple_bonds(filter=filter) :
      atom1 = atoms[i_seq].fetch_labels()
      atom2 = atoms[j_seq].fetch_labels()
      base_sele = """chain "%s" and resi %s and name %s"""
      sele1 = base_sele % (atom1.chain_id, atom1.resseq, atom1.name)
      sele2 = base_sele % (atom2.chain_id, atom2.resseq, atom2.name)
      print >>out, "dist %s, %s" % (sele1, sele2)

def hydrogen_bonds_from_selections (
    pdb_hierarchy,
    params,
    log=sys.stderr) :
  bond_i_seqs = shared.stl_set_unsigned()
  sigmas = flex.double()
  slacks = flex.double()
  atoms = pdb_hierarchy.atoms()
  n_atoms = atoms.size()
  sites = atoms.extract_xyz()
  has_bond = flex.bool(sites.size(), False)
  selection_cache = pdb_hierarchy.atom_selection_cache()
  isel = selection_cache.iselection
  donor_name = "H"
  distance_ideal = params.h_bond_restraints.h_o_distance_ideal
  if params.h_bond_restraints.substitute_n_for_h :
    distance_ideal = params.h_bond_restraints.n_o_distance_ideal
    donor_name = "N"
  if params.h_bond_restraints.restrain_helices :
    for helix in params.helix :
      helix_class = int(helix.helix_class)
      if helix_class != 1 and params.h_bond_restraints.alpha_only :
        print >> log, "Skipping non-alpha helix (class %d):" % helix_class
        print >> log, "  %s" % helix.selection
        continue
      try :
        donor_isel, acceptor_isel = _donors_and_acceptors(
          base_sele=helix.selection,
          selection_cache=selection_cache,
          atoms=atoms,
          donor_name=donor_name,
          ss_type="helix")
      except RuntimeError, e :
        print >> log, str(e)
        continue
      else :
        if helix_class == 1 :
          j = 4
        elif helix_class == 3 :
          j = 5
        elif helix_class == 5 :
          j = 3
        else :
          print >> log, "Don't know bonding for helix class %d." % helix_class
          continue
        sigma = params.h_bond_restraints.sigma
        if helix.restraint_sigma is not None :
          sigma = helix.restraint_sigma
        elif sigma is None :
          raise Sorry(("Please either set the global sigma for hydrogen bond "+
            "restraints, or set the sigma for helix '%s'.") % helix.selection)
        slack = params.h_bond_restraints.slack
        if helix.restraint_slack is not None :
          slack = helix.restraint_slack
        elif slack is None :
          raise Sorry(("Please either set the global slack for hydrogen bond "+
            "restraints, or set the slack for helix '%s'.") % helix.selection)
        n_donors = acceptor_isel.size()
        for n, i_seq in enumerate(acceptor_isel) :
          if (n + j) < n_donors :
            j_seq =  donor_isel[n+j]
            if j_seq == n_atoms :
              continue # dummy index - missing H from PRO
            elif atoms[j_seq].fetch_labels().resname == "PRO" :
              print >> log, "Skipping proline residue in middle of helix:"
              print >> log, "  %s" % atoms[j_seq].fetch_labels().id_str()
              continue
            if has_bond[i_seq] or has_bond[j_seq] :
              print >> log, "One or more atoms already bonded:"
              print >> log, "  %s" % atoms[i_seq].fetch_labels().id_str()
              print >> log, "  %s" % atoms[j_seq].fetch_labels().id_str()
              continue
            has_bond[i_seq] = True
            has_bond[j_seq] = True
            bond_i_seqs.append((j_seq, i_seq))
            sigmas.append(sigma)
            slacks.append(slack)
          else :
            break
  if params.h_bond_restraints.restrain_sheets :
    for i_sheet, sheet in enumerate(params.sheet) :
      if sheet.first_strand is None :
        raise Sorry("First strand must be a valid atom selection.")
      sheet_bonds = []
      prev_strand_sele = sheet.first_strand
      for curr_strand in sheet.strand :
        if curr_strand.selection is None :
          raise Sorry("All strands must have a valid atom selection.")
        elif curr_strand.bond_start_current is None :
          raise Sorry("Missing start of bonding for strand '%s'." %
            curr_strand.selection)
        elif curr_strand.bond_start_previous is None :
          raise Sorry("Missing start of bonding for strand previous to '%s'." %
            curr_strand.selection)
        try :
          if curr_strand.sense == "unknown" :
            raise RuntimeError(("Skipping strand of unknown sense:\n" +
              "%s") % curr_strand.selection)
          curr_donors, curr_acceptors = _donors_and_acceptors(
            base_sele=curr_strand.selection,
            selection_cache=selection_cache,
            atoms=atoms,
            donor_name=donor_name,
            ss_type="sheet")
          prev_donors, prev_acceptors = _donors_and_acceptors(
            base_sele=prev_strand_sele,
            selection_cache=selection_cache,
            atoms=atoms,
            donor_name=donor_name,
            ss_type="sheet")
          curr_donor_start, curr_acceptor_start = _donors_and_acceptors(
            base_sele=curr_strand.bond_start_current,
            selection_cache=selection_cache,
            atoms=atoms,
            donor_name=donor_name,
            ss_type="sheet")
          prev_donor_start, prev_acceptor_start = _donors_and_acceptors(
            base_sele=curr_strand.bond_start_previous,
            selection_cache=selection_cache,
            atoms=atoms,
            donor_name=donor_name,
            ss_type="sheet")
          new_bonds = _hydrogen_bonds_from_strand_pair(atoms=atoms,
            prev_strand_donors=prev_donors,
            prev_strand_acceptors=prev_acceptors,
            prev_strand_start=prev_donor_start[0],
            curr_strand_donors=curr_donors,
            curr_strand_acceptors=curr_acceptors,
            curr_strand_start=curr_acceptor_start[0],
            sense=curr_strand.sense)
          if new_bonds is None :
            raise RuntimeError(
              ("Can't determine start of bonding for strand pair:\n" +
              "  %s\n  %s\n") % (prev_strand_sele, curr_strand.selection))
          elif len(new_bonds) == 0 :
            raise RuntimeError(("No bonds found for strand pair:\n"+
              "  %s\n  %s\n") % (prev_strand_sele, curr_strand.selection))
          sheet_bonds.extend(new_bonds)
        except RuntimeError, e :
          print >> log, str(e)
        finally :
          prev_strand_sele = curr_strand.selection
      sigma = params.h_bond_restraints.sigma
      if sheet.restraint_sigma is not None :
        sigma = sheet.restraint_sigma
      elif sigma is None :
        raise Sorry(("Please either set the global sigma for hydrogen bond "+
          "restraints, or set the sigma for sheet #%d.") % i_sheet)
      slack = params.h_bond_restraints.slack
      if sheet.restraint_slack is not None :
        slack = sheet.restraint_slack
      elif slack is None :
        raise Sorry(("Please either set the global slack for hydrogen bond "+
          "restraints, or set the slack for sheet #%d.") % i_sheet)
      for (i_seq, j_seq) in sheet_bonds :
        if has_bond[i_seq] or has_bond[j_seq] :
          print >> log, "One or more atoms already bonded:"
          print >> log, "  %s" % atoms[i_seq].fetch_labels().id_str()
          print >> log, "  %s" % atoms[j_seq].fetch_labels().id_str()
          continue
        has_bond[i_seq] = True
        has_bond[j_seq] = True
        bond_i_seqs.append((i_seq, j_seq))
        sigmas.append(sigma)
        slacks.append(slack)
  return hydrogen_bond_table(bonds=bond_i_seqs,
    distance=flex.double(bond_i_seqs.size(), distance_ideal),
    sigma=sigmas,
    slack=slacks,
    bond_lengths=_get_distances(bond_i_seqs, sites))

def _get_distances (bonds, sites_cart) :
  distances = flex.double(bonds.size(), -1)
  for k, (i_seq, j_seq) in enumerate(bonds) :
    (x1, y1, z1) = sites_cart[i_seq]
    (x2, y2, z2) = sites_cart[j_seq]
    dist = sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)
    distances[k] = dist
  return distances

def _donors_and_acceptors (base_sele, selection_cache, atoms, donor_name,
    ss_type) :
  isel = selection_cache.iselection
  donor_sele = "(%s) and (altloc 'A' or altloc ' ') and name %s" % (
    base_sele, donor_name)
  acceptor_sele = "(%s) and (altloc 'A' or altloc ' ') and name O"% base_sele
  donor_isel = isel(donor_sele)
  acceptor_isel = isel(acceptor_sele)
  n_donors = donor_isel.size()
  n_acceptors = acceptor_isel.size()
  n_atoms = atoms.size()
  if n_acceptors == 0 :
    raise RuntimeError("No atoms for selection %s." % acceptor_sele)
  elif n_donors != n_acceptors :
    n_pro = 0
    for k, i_seq in enumerate(acceptor_isel) :
      acceptor_atom = atoms[i_seq].fetch_labels()
      if acceptor_atom.resname.strip() == "PRO" :
        donor_isel.insert(k, n_atoms)
        n_pro += 1
    if (n_donors + n_pro) != n_acceptors :
      raise RuntimeError("""\
hydrogen_bonds_from_selections: incomplete non-PRO residues in %s.
  \"%s\" => %d donors
  \"%s\" => %d acceptors""" % (ss_type, donor_sele, donor_isel.size(),
      acceptor_sele, acceptor_isel.size()))
  return donor_isel, acceptor_isel

def _hydrogen_bonds_from_strand_pair (atoms,
    prev_strand_donors,
    prev_strand_acceptors,
    prev_strand_start,
    curr_strand_donors,
    curr_strand_acceptors,
    curr_strand_start,
    sense) :
  n_atoms = atoms.size()
  assert sense != "unknown"
  assert prev_strand_donors.size() == prev_strand_acceptors.size()
  assert curr_strand_donors.size() == curr_strand_acceptors.size()
  start_bonding = False
  bonds = []
  n_prev_strand = prev_strand_donors.size()
  n_curr_strand = curr_strand_donors.size()
  i = j = None
  for k, donor_i_seq in enumerate(prev_strand_donors) :
    if donor_i_seq == prev_strand_start :
      i = k
      break
  #print curr_strand_start, curr_strand_acceptors
  for k, acceptor_i_seq in enumerate(curr_strand_acceptors) :
    if acceptor_i_seq == curr_strand_start :
      j = k
      break
  if None in [i, j] :
    return None
  if sense == "antiparallel" :
    while i < n_prev_strand and j > 0 :
      donor1_i_seq = prev_strand_donors[i]
      acceptor1_i_seq = curr_strand_acceptors[j]
      if (donor1_i_seq != n_atoms and
          atoms[donor1_i_seq].fetch_labels().resname.strip() != "PRO") :
        bonds.append((donor1_i_seq, acceptor1_i_seq))
      donor2_i_seq = curr_strand_donors[j]
      acceptor2_i_seq = prev_strand_acceptors[i]
      if (donor2_i_seq != n_atoms and
          atoms[donor2_i_seq].fetch_labels().resname.strip() != "PRO") :
        bonds.append((donor2_i_seq, acceptor2_i_seq))
      i += 2
      j -= 2
  else :
    while i < n_prev_strand and j < n_curr_strand :
      donor1_i_seq = prev_strand_donors[i]
      acceptor1_i_seq = curr_strand_acceptors[j]
      if (donor1_i_seq != n_atoms and
          atoms[donor1_i_seq].fetch_labels().resname.strip() != "PRO") :
        bonds.append((donor1_i_seq, acceptor1_i_seq))
      if (j + 2) >= n_curr_strand :
        break
      donor2_i_seq = curr_strand_donors[j+2]
      acceptor2_i_seq = prev_strand_acceptors[i]
      if (donor2_i_seq != n_atoms and
          atoms[donor2_i_seq].fetch_labels().resname.strip() != "PRO") :
        bonds.append((donor2_i_seq, acceptor2_i_seq))
      i += 2
      j += 2
  return bonds

def _hydrogen_bond_from_selection_pair (donor_sele, acceptor_sele,
    selection_cache) :
  donor_i_seqs = isel(donor_sele)
  acceptor_i_seqs = isel(acceptor_sele)
  n_donor_sel = donor_i_seqs.size()
  n_acceptor_sel = acceptor_i_seqs.size()
  if n_donor_sel == 0 or n_acceptor_sel == 0 :
    raise RuntimeError("""\
analyze_h_bonds: one or more atoms missing
  %s (%d atoms)
  %s (%d atoms)""" % (donor_sele, n_donor_sel, acceptor_sele, n_acceptor_sel))
  elif n_donor_sel > 1 or n_acceptor_sel > 1 :
    raise RuntimeError("""\
analyze_h_bonds: multiple atoms matching a selection
  %s (%d atoms)
  %s (%d atoms)""" % (donor_sele, n_donor_sel, acceptor_sele, n_acceptor_sel))
  return (donor_i_seqs[0], acceptor_i_seqs[0])

def get_pdb_hierarchy (file_names) :
  import iotbx.pdb
  from scitbx.array_family import flex
  pdb_combined = iotbx.pdb.combine_unique_pdb_files(file_names=file_names)
  pdb_structure = iotbx.pdb.input(source_info=None,
    lines=flex.std_string(pdb_combined.raw_records))
  return pdb_structure.construct_hierarchy()

def restraint_groups_as_pdb_helices (pdb_hierarchy, helices, log=sys.stderr) :
  isel = pdb_hierarchy.atom_selection_cache().iselection
  atoms = [ a for a in pdb_hierarchy.atoms_with_labels() ]
  pdb_helices = []
  for i, helix_params in enumerate(helices) :
    if helix_params.selection is None :
      print >> log, "Empty helix at serial %d." % (i+1)
      continue
    sele_str = ("(%s) and name N and (altloc 'A' or altloc ' ')" %
                helix_params.selection)
    amide_isel = isel(sele_str)
    start_atom = atoms[amide_isel[0]]
    end_atom = atoms[amide_isel[-1]]
    current_helix = iotbx.pdb.secondary_structure.pdb_helix(
      serial=i+1,
      helix_id=i+1,
      start_resname=start_atom.resname,
      start_chain_id=start_atom.chain_id,
      start_resseq=start_atom.resseq,
      start_icode=start_atom.icode,
      end_resname=end_atom.resname,
      end_chain_id=end_atom.chain_id,
      end_resseq=end_atom.resseq,
      end_icode=end_atom.icode,
      helix_class=int(helix_params.helix_class),
      comment="",
      length=amide_isel.size())
    pdb_helices.append(current_helix)
  return pdb_helices

def restraint_groups_as_pdb_sheets (pdb_hierarchy, sheets, log=sys.stderr) :
  isel = pdb_hierarchy.atom_selection_cache().iselection
  atoms = [ a for a in pdb_hierarchy.atoms_with_labels() ]
  pdb_sheets = []
  for i, sheet in enumerate(sheets) :
    sheet_id = string.uppercase[i]
    if sheet.first_strand is None :
      print >> log, "Missing first strand in sheet %s" % sheet_id
    current_sheet = iotbx.pdb.secondary_structure.pdb_sheet(
      sheet_id=sheet_id,
      n_strands=1+len(sheet.strand),
      strands=[],
      registrations=[])
    first_strand = __strand_group_as_pdb_strand(isel=isel,
      selection=sheet.first_strand,
      atoms=atoms,
      log=log,
      sense=None)
    current_sheet.add_strand(first_strand)
    current_sheet.add_registration(None)
    base_sele = "(%s) and name N and (altloc 'A' or altloc ' ')"
    for strand in sheet.strand :
      pdb_strand = __strand_group_as_pdb_strand(isel=isel,
        selection=strand.selection,
        atoms=atoms,
        log=log,
        sense=strand.sense)
      current_sheet.add_strand(pdb_strand)
      s1 = base_sele % strand.bond_start_current
      s2 = base_sele % strand.bond_start_previous
      reg_curr_isel = isel(s1)
      reg_prev_isel = isel(s2)
      if reg_curr_isel.size() == 0 or reg_prev_isel.size() == 0 :
        current_sheet.add_registration(None)
        continue
      reg_curr_atom = atoms[reg_curr_isel[0]]
      reg_prev_atom = atoms[reg_prev_isel[0]]
      registration = group_args(
        cur_atom=donor_name, #reg_curr_atom.name,
        cur_resname=reg_curr_atom.resname,
        cur_chain_id=reg_curr_atom.chain_id,
        cur_resseq=reg_curr_atom.resseq,
        cur_icode=reg_curr_atom.icode,
        prev_atom=reg_prev_atom.name,
        prev_resname="O", #reg_prev_atom.resname,
        prev_chain_id=reg_prev_atom.chain_id,
        prev_resseq=reg_prev_atom.resseq,
        prev_icode=reg_prev_atom.icode)
      current_sheet.add_registration(registration)
    pdb_sheets.append(current_sheet)
  return pdb_sheets

def __strand_group_as_pdb_strand (isel, selection, atoms, log, sense) :
  if sense is None or sense == "unknown" :
    int_sense = 0
  elif sense == "parallel" :
    int_sense = 1
  elif sense == "antiparallel" :
    int_sense = -1
  strand_isel = isel("(%s) and name N and (altloc 'A' or altloc ' ')" % (
    selection))
  start_atom = atoms[strand_isel[0]]
  end_atom = atoms[strand_isel[-1]]
  pdb_strand = group_args(
    sheet_id=sheet_id,
    strand_id=i+1,
    start_resname=start_atom.resname,
    start_chain_id=start_atom.chain_id,
    start_resseq=start_atom.resseq,
    start_icode=start_atom.icode,
    end_resname=end_atom.resname,
    end_chain_id=end_atom.chain_id,
    end_resseq=end_atom.resseq,
    end_icode=end_atom.icode,
    sense=int_sense)
  return pdb_strand

class manager (object) :
  def __init__ (self,
                pdb_hierarchy,
                xray_structure,
                sec_str_from_pdb_file=None,
                params=None,
                assume_hydrogens_all_missing=None,
                tmp_dir=None) :
    adopt_init_args(self, locals())
    if self.params is None :
      self.params = default_params
    if self.tmp_dir is None :
      self.tmp_dir = os.getcwd()
    if self.assume_hydrogens_all_missing is None :
      xrs = self.xray_structure
      sctr_keys = xrs.scattering_type_registry().type_count_dict().keys()
      self.assume_hydrogens_all_missing = not ("H" in sctr_keys or
        "D" in sctr_keys)
    if self.params.h_bond_restraints.substitute_n_for_h is None :
      self.params.h_bond_restraints.substitute_n_for_h = \
        self.assume_hydrogens_all_missing

  def find_automatically (self, log=sys.stderr) :
    params = self.params
    find_automatically = params.input.find_automatically
    if len(params.helix) == 0 and len(params.sheet) == 0 :
      if self.sec_str_from_pdb_file is None and find_automatically != False :
        find_automatically = True
      elif find_automatically != True :
        self.sec_str_from_pdb_file = None # disable this
    if find_automatically :
      self.sec_str_from_pdb_file = self.find_sec_str()
    if self.sec_str_from_pdb_file is not None :
      print >> log, "  Interpreting HELIX and SHEET records from PDB file"
      ss_params_str = self.sec_str_from_pdb_file.as_restraint_groups(log=log,
        prefix_scope="")
      self.apply_phil_str(ss_params_str, log=log)

  def find_sec_str (self) :
    tmp_file = ".dssp.%d.pdb" % os.getpid()
    open(tmp_file, "w").write(acp.pdb_hierarchy.as_pdb_string())
    records = run_ksdssp(tmp_file, log=log)
    sec_str_from_pdb_file = iotbx.pdb.secondary_structure.process_records(
      records=records)
    os.remove(tmp_file)
    return sec_str_from_pdb_file

  def apply_phil_str (self, phil_string, log=sys.stderr, verbose=True) :
    ss_phil = libtbx.phil.parse(phil_string)
    if verbose :
      ss_phil.show(out=log, prefix="    ")
    new_ss_params = sec_str_master_phil.fetch(source=ss_phil).extract()
    self.params = new_ss_params

  def get_bonds_table (self, log=sys.stderr, verbose=True) :
    params = self.params
    bonds_table = hydrogen_bonds_from_selections(
      pdb_hierarchy=self.pdb_hierarchy,
      params=params,
      log=log)
    if verbose :
      print >> log, ""
      print >> log, "  Found %d helices and %d sheets." % (len(params.helix),
        len(params.sheet))
      print >> log, "  %d hydrogen bonds defined." % bonds_table.bonds.size()
    bonds_table.analyze_distances(params=params.h_bond_restraints,
      pdb_hierarchy=self.pdb_hierarchy,
      log=log)
    if verbose :
      print >> log, ""
    return bonds_table

def process_structure (params, processed_pdb_file, tmp_dir, log,
    assume_hydrogens_all_missing=None, return_bonds=True) :
  acp = processed_pdb_file.all_chain_proxies
  sec_str_from_pdb_file = acp.extract_secondary_structure()
  pdb_hierarchy = acp.pdb_hierarchy
  xray_structure = acp.extract_xray_structure()
  structure_manager = manager(
    pdb_hierarchy=pdb_hierarchy,
    xray_structure=xray_structure,
    sec_str_from_pdb_file=sec_str_from_pdb_file,
    params=params,
    assume_hydrogens_all_missing=assume_hydrogens_all_missing,
    tmp_dir=tmp_dir)
  structure_manager.find_automatically(log=log)
  if return_bonds :
    bonds_table = structure_manager.get_bonds_table(log=log)
    return bonds_table
  else :
    return structure_manager

def run_ksdssp (file_name, log=sys.stderr) :
  if not os.path.isfile(file_name) :
    raise Sorry("File %s not found.")
  exe_path = libtbx.env.under_build("ksdssp/exe/ksdssp")
  if not os.path.isfile(exe_path) :
    raise Sorry("KSDSSP not available.")
  print >> log, "  Running KSDSSP to generate HELIX and SHEET records for %s"%\
    os.path.basename(file_name)
  ksdssp_out = easy_run.fully_buffered(command="%s %s" % (exe_path, file_name))
  if len(ksdssp_out.stderr_lines) > 0 :
    print >> log, "\n".join(ksdssp_out.stderr_lines)
  return ksdssp_out.stdout_lines

def run (args, out=sys.stdout, log=sys.stderr) :
  pdb_files = []
  sources = []
  force_new_annotation = False
  master_phil = libtbx.phil.parse("""
    show_histograms = False
      .type = bool
    show_pymol_dashes = False
      .type = bool
%s""" % sec_str_master_phil_str)
  for arg in args :
    if os.path.isfile(arg) :
      if iotbx.pdb.is_pdb_file(arg) :
        pdb_files.append(os.path.abspath(arg))
    elif arg == "--run_ksdssp" :
      force_new_annotation = True
    else :
      if arg.startswith("--") :
        arg = arg[2:] + "=True"
      sources.append(libtbx.phil.parse(arg))
  params = master_phil.fetch(sources=sources).extract()
  secondary_structure = None
  if len(pdb_files) == 0 :
    raise Usage("phenix.secondary_structure_restraints model.pdb")
  elif not force_new_annotation :
    secondary_structure = iotbx.pdb.secondary_structure.process_records(
      pdb_files=pdb_files)
  if force_new_annotation or secondary_structure is None :
    records = run_ksdssp(pdb_files[0], log=log)
    secondary_structure = iotbx.pdb.secondary_structure.process_records(
      records=records, allow_none=False)
  prefix_scope="refinement.secondary_structure"
  if params.show_histograms or params.show_pymol_dashes :
    prefix_scope = ""
  ss_params_str = secondary_structure.as_restraint_groups(log=log,
    prefix_scope=prefix_scope)
  ss_phil = libtbx.phil.parse(ss_params_str)
  if params.show_pymol_dashes :
    working_phil = master_phil.fetch(sources=[ss_phil]+sources)
    params = working_phil.extract()
    pdb_hierarchy = get_pdb_hierarchy(pdb_files)
    bonds_table = hydrogen_bonds_from_selections(
      pdb_hierarchy,
      params=params,
      log=sys.stderr)
    bonds_table.analyze_distances(params=params.h_bond_restraints,
      pdb_hierarchy=pdb_hierarchy,
      log=sys.stderr)
    bonds_table.as_pymol_dashes(pdb_hierarchy, filter=True, out=out)
  elif params.show_histograms :
    working_phil = master_phil.fetch(sources=[ss_phil]+sources)
    working_phil.show()
    print >> out, ""
    print >> out, "========== Analyzing hydrogen bonding distances =========="
    print >> out, ""
    params = working_phil.extract()
    pdb_hierarchy = get_pdb_hierarchy(pdb_files)
    bonds_table = hydrogen_bonds_from_selections(
      pdb_hierarchy,
      params=params,
      log=out)
    bonds_table.analyze_distances(params=params.h_bond_restraints,
      pdb_hierarchy=pdb_hierarchy,
      log=out)
  else :
    ss_phil.show(out=out)
    #print >> out, ss_params_str

def get_bonds (file_name, out=sys.stdout, log=sys.stderr,
    force_new_annotation=False, fake_hydrogens=True) :
  records = None
  if force_new_annotation :
    records = run_ksdssp(file_name, log=log)
  secondary_structure = iotbx.pdb.secondary_structure.process_records(
    records=records,
    pdb_files=[file_name])
  assert secondary_structure is not None
  ss_params_str = secondary_structure.as_restraint_groups(log=sys.stderr)
  pdb_hierarchy = get_pdb_hierarchy([file_name])
  sources = [libtbx.phil.parse(ss_params_str)]
  working_phil = sec_str_master_phil.fetch(sources=sources)
  #working_phil.show()
  params = working_phil.extract()
  params.h_bond_restraints.substitute_n_for_h = fake_hydrogens
  bonds_table = hydrogen_bonds_from_selections(
    pdb_hierarchy,
    params=params,
    log=log)
  return pdb_hierarchy, bonds_table

def exercise () :
  pdb_file = libtbx.env.find_in_repositories(
    relative_path="phenix_regression/pdb/1ywf.pdb",
    test=os.path.isfile)
  pdb_file_h = libtbx.env.find_in_repositories(
    relative_path="phenix_regression/pdb/1ywf_h.pdb",
    test=os.path.isfile)
  if pdb_file is None :
    print "Skipping"
    return False
  log = cStringIO.StringIO()
  params = sec_str_master_phil.extract()
  pdb_hierarchy, bonds_table = get_bonds(pdb_file, log=log)
  atoms = pdb_hierarchy.atoms()
  assert bonds_table.bonds.size() == 109
  params.h_bond_restraints.substitute_n_for_h = True
  bonds_table.analyze_distances(params=params.h_bond_restraints,
    pdb_hierarchy=pdb_hierarchy,
    log=log)
  assert bonds_table.flag_use_bond.count(True) == 106
  pdb_hierarchy, bonds_table_new = get_bonds(pdb_file, log=log,
    force_new_annotation=True)
  assert bonds_table_new.bonds.size() == 93
  pdb_hierarchy, bonds_table = get_bonds(pdb_file_h, log=log,
    fake_hydrogens=False)
  assert bonds_table.bonds.size() == 109
  params.h_bond_restraints.substitute_n_for_h = False
  bonds_table.analyze_distances(params=params.h_bond_restraints,
    pdb_hierarchy=pdb_hierarchy,
    log=log)
  assert bonds_table.flag_use_bond.count(True) == 103
  print "OK"

if __name__ == "__main__" :
  if "--test" in sys.argv :
    exercise()
  else :
    run(sys.argv[1:])
