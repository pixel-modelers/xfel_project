from __future__ import division
import os
import mmtbx.model
import libtbx.load_env
from mmtbx import monomer_library
import mmtbx.monomer_library.server
import mmtbx.monomer_library.pdb_interpretation
from mmtbx import ias


def exercise():
  # initial setup
  mon_lib_srv = monomer_library.server.server()
  ener_lib = monomer_library.server.ener_lib()
  cif_file = libtbx.env.find_in_repositories(
            relative_path="phenix_regression/pdb/tyr.cif", test=os.path.isfile)
  mon_lib_srv.process_cif(file_name= cif_file)
  ener_lib.process_cif(file_name= cif_file)
  pdb_file = libtbx.env.find_in_repositories(
            relative_path="phenix_regression/pdb/ygg.pdb", test=os.path.isfile)
  processed_pdb_file = monomer_library.pdb_interpretation.process(
                                       mon_lib_srv               = mon_lib_srv,
                                       ener_lib                  = ener_lib,
                                       file_name                 = pdb_file,
                                       raw_records               = None,
                                       force_symmetry            = True)
  xray_structure = processed_pdb_file.xray_structure()
  geometry = processed_pdb_file.geometry_restraints_manager(
                                                    show_energies      = True,
                                                    plain_pairs_radius = 5.0)
  restraints_manager = mmtbx.restraints.manager(geometry      = geometry,
                                                normalization = False)
  bond_proxies_simple, asu = geometry.get_covalent_bond_proxies(
                  sites_cart = xray_structure.sites_cart())

  # get ias manager
  params = ias.ias_master_params.extract()
  pdb_hierarchy = processed_pdb_file.all_chain_proxies.pdb_hierarchy
  all = ias.ias_master_params.extract().build_ias_types
  for opt in [["L"], ["R"], ["B"], ["BH"], all]:
    mol = mmtbx.model.manager(
      restraints_manager = restraints_manager,
      xray_structure = xray_structure,
      pdb_hierarchy = pdb_hierarchy).deep_copy()
    if(opt == ["L"]):
      params.build_ias_types = opt
      mol.add_ias(fmodel = None, ias_params = params)
      f = open("zz.pdb","w")
      pdb_str = mol.model_as_pdb()
      f.write(pdb_str)
      f.close()
      assert mol.ias_selection.size() == 47, mol.ias_selection.size()
      assert mol.ias_selection.count(True) == 6, mol.ias_selection.count(True)
      assert mol.ias_selection.count(False) == 41, mol.ias_selection.count(False)
    if(opt == all):
      params.build_ias_types = opt
      mol.add_ias(fmodel = None, ias_params = params)
      assert mol.ias_selection.size() == 88,mol.ias_selection.size()
      assert mol.ias_selection.count(True) == 47
      assert mol.ias_selection.count(False) == 41
    if(opt == ["R"]):
      params.build_ias_types = opt
      mol.add_ias(fmodel = None, ias_params = params)
      assert mol.ias_selection.size() == 42
      assert mol.ias_selection.count(True) == 1
      assert mol.ias_selection.count(False) == 41
    if(opt == ["B"]):
      params.build_ias_types = opt
      mol.add_ias(fmodel = None, ias_params = params)
      assert mol.ias_selection.size() == 62
      assert mol.ias_selection.count(True) == 21
      assert mol.ias_selection.count(False) == 41
    if(opt == ["BH"]):
      params.build_ias_types = opt
      mol.add_ias(fmodel = None, ias_params = params)
      assert mol.ias_selection.size() == 60
      assert mol.ias_selection.count(True) == 19
      assert mol.ias_selection.count(False) == 41

def run():
  exercise()

if (__name__ == "__main__"):
  run()
  print "OK"
