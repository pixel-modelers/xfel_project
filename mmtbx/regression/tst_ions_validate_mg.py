
from __future__ import division
from libtbx import easy_run
import time

def exercise () :
  from mmtbx.regression.make_fake_anomalous_data import generate_magnessium_inputs
  mtz_file, pdb_file = generate_magnessium_inputs(
      file_base = "tst_ions_validate_mg", anonymize = False)
  time.sleep(2)
  args = [pdb_file, mtz_file, "nproc=1"]
  result = easy_run.fully_buffered("mmtbx.validate_ions %s" % " ".join(args)
    ).raise_if_errors()
  n_mg, n_bad = 0, 0
  for line in result.stdout_lines :
    if "| MG" in line:
      n_mg += 1
    if "!!!" in line:
      n_bad += 1
  assert n_mg == 2 and n_bad == 0
  print "OK"

if (__name__ == "__main__") :
  exercise()
