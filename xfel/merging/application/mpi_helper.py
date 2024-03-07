from __future__ import absolute_import, division, print_function
from six.moves import range
from libtbx.mpi4py import MPI
import numpy as np
from dials.array_family import flex

import sys
def system_exception_handler(exception_type, value, traceback):
  try:
    rank = MPI.COMM_WORLD.Get_rank()
    from traceback import print_exception
    sys.stderr.write("\nTrying to abort all MPI processes because of exception in process %d:\n"%rank)
    print_exception(exception_type, value, traceback)
    sys.stderr.write("\n")
    sys.stderr.flush()
  finally:
    try:
      MPI.COMM_WORLD.Abort(1)
    except Exception as e:
      sys.stderr.write("\nFailed to execute: MPI.COMM_WORLD.Abort(1)\n")
      sys.stderr.flush()
      raise e
sys.excepthook = system_exception_handler

class mpi_helper(object):
  def __init__(self):
    self.MPI = MPI
    self.comm = self.MPI.COMM_WORLD
    self.rank = self.comm.Get_rank()
    self.size = self.comm.Get_size()
    self.error = (None,None) # (rank,description)

  def time(self):
    return self.MPI.Wtime()

  def finalize(self):
    self.MPI.Finalize()

  def cumulative_flex(self, flex_array, flex_type):
    '''Build a cumulative sum flex array out of multiple same-size flex arrays.'''
    # Example: (a1,a2,a3) + (b1, b2, b3) = (a1+b1, a2+b2, a3+b3)
    if self.rank == 0:
      cumulative = flex_type(flex_array.size(), 0)
    else:
      cumulative = None

    list_of_all_flex_arrays = self.comm.gather(flex_array, 0)

    if self.rank == 0:
      for i in range(len(list_of_all_flex_arrays)):
        flex_array = list_of_all_flex_arrays[i]
        if flex_array is not None:
          cumulative += flex_array

    return cumulative

  def aggregate_flex(self, flex_array, flex_type):
    '''Build an aggregate flex array out of multiple flex arrays'''
    # Example: (a1,a2,a3) + (b1, b2, b3) = (a1, a2, a3, b1, b2, b3)
    if self.rank == 0:
      aggregate = flex_type()
    else:
      aggregate = None

    list_of_all_flex_arrays = self.comm.gather(flex_array, 0)

    if self.rank == 0:
      for i in range(len(list_of_all_flex_arrays)):
        flex_array = list_of_all_flex_arrays[i]
        if flex_array is not None:
          aggregate.extend(flex_array)

    return aggregate

  def sum(self, data, root=0):
    return self.comm.reduce(data, self.MPI.SUM, root=root)

  def set_error(self, description):
    self.error = (self.rank, description)

  def check_errors(self):
    all_errors = self.comm.allreduce([self.error], self.MPI.SUM)
    actual_errors = [error for error in all_errors if error != (None,None)]
    if len(actual_errors) > 0:
      sys.stderr.write("\nAborting MPI process %d because of the following error(s):"%self.rank)
      for error in actual_errors:
        sys.stderr.write("\nError reported by process %d: %s\n"%(error[0], error[1]))
      sys.stderr.flush()
      self.comm.Abort(1)

  def gather_variable_length_numpy_arrays(self, send_arrays, root=0, dtype=float):
    lengths = self.comm.gather(send_arrays.size, root=root)
    if self.rank == root:
      gathered_arrays = np.empty(np.sum(lengths), dtype=dtype)
    else:
      gathered_arrays = None
    self.comm.Gatherv(sendbuf=send_arrays, recvbuf=(gathered_arrays, lengths), root=root)
    return gathered_arrays
