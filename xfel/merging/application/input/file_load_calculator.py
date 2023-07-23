from __future__ import absolute_import, division, print_function
from six.moves import range
import sys
import os
from xfel.merging.application.input.file_lister import list_input_pairs

debug=False # set debug=True, if you want to see a per-rank experiments/reflections file pair list generated by this calculator
available_rank_count = 0  # used only when running this script stand-alone:
                          # if input.parallel_file_load.method=uniform, set this to the available rank count
                          # if input.parallel_file_load.method=node_memory, leave it at zero and the calculator will determine how many nodes you need

b2GB = 1024 * 1024 * 1024 # byte to GB

class file_load_calculator(object):
  def __init__(self, params, file_list, logger=None):
    self.params = params
    self.file_list = file_list
    self.logger = logger
    global debug
    if debug:
      self.debug_log_path = os.path.join(self.params.output.output_dir, 'file_load_calculator.out')
      assert not os.path.exists(self.debug_log_path), "\n\nFile %s already exists. Please either remove this file or set debug=False in file_load_calculator.py and try again.\n"%self.debug_log_path
    else:
      self.debug_log_path = None

  def debug_log_write(self, string):
    if not debug:
      return
    debug_log_file_handle = open(self.debug_log_path, 'a')
    debug_log_file_handle.write(string)
    debug_log_file_handle.close()

  def calculate_file_load(self, available_rank_count=0):
    '''Calculate a load and build a dictionary {rank:file_list} for the input number of ranks'''
    if self.logger:
      self.logger.log_step_time("CALCULATE_FILE_LOAD")
    rank_files = {}
    if self.params.input.parallel_file_load.method == "uniform":
      rank_files = self.calculate_file_load_simple(available_rank_count)
    elif self.params.input.parallel_file_load.method == "node_memory":
      rank_files = self.calculate_file_load_node_memory_based(available_rank_count)

    if debug:
      for rank in range(len(rank_files)):
        self.debug_log_write("\nRank %d"%rank)
        for file_pair in rank_files[rank]:
          self.debug_log_write("\n%s"%str(file_pair))

    total_file_pairs = 0
    for key, value in rank_files.items():
      total_file_pairs += len(value)

    if self.logger:
      self.logger.log("Generated a list of %d file items for %d ranks"%(total_file_pairs, len(rank_files)))
      self.logger.log_step_time("CALCULATE_FILE_LOAD", True)

    return rank_files

  def calculate_file_load_simple(self, available_rank_count):
    '''Uniformly distribute experiments/reflections file pairs over the input number of ranks. Return a dictionary {rank:filepair_list}'''
    assert available_rank_count > 0, "Available rank count has to be greater than zero."
    rank_files = {} #{rank:[file_pair1, file_pair2, ...]}
    for rank in range(0, available_rank_count):
      rank_files[rank] = self.file_list[rank::available_rank_count]

    return rank_files

  def calculate_file_load_node_memory_based(self, available_rank_count):
    '''Assign experiments/reflections file pairs to nodes taking into account the node memory limit. Then distribute node-assigned file pairs over the ranks within each node. Return a dictionary {rank:file_list}'''
    # get sizes of all files
    file_sizes = {} # {file_pair:file_pair_size_GB}
    for index in range(len(self.file_list)):
      file_sizes[self.file_list[index]] = os.stat(self.file_list[index][1]).st_size / b2GB # [1] means: use only the reflection file size for now

    # assign files to the anticipated nodes - based on the file sizes and the node memory limit
    node_files = {} # {node:[file_pair1, file_pair2,...]}
    node = 0
    node_files[node] = []
    anticipated_memory_usage_GB = 0
    for file_pair in file_sizes:
      anticipated_memory_usage_GB += (file_sizes[file_pair] * self.params.input.parallel_file_load.node_memory.pickle_to_memory)
      if anticipated_memory_usage_GB < self.params.input.parallel_file_load.node_memory.limit: # keep appending the files as long as the total anticipated memory doesn't exceed the node memory limit
        node_files[node].append(file_pair)
      else:
        node += 1
        node_files[node] = []
        node_files[node].append(file_pair)
        anticipated_memory_usage_GB = (file_sizes[file_pair] * self.params.input.parallel_file_load.node_memory.pickle_to_memory)

    # now we know how many nodes are required
    required_number_of_nodes = len(node_files)
    print("\nMinimum required number of nodes for mpi.merge: %d\n"%required_number_of_nodes)

    # for each node evenly distribute the files over the ranks
    rank_files = {} #{rank:[file_pair1, file_pair2, ...]}
    rank_base = 0 # the first rank of a node
    required_number_of_ranks = 0 # on all nodes
    for node in range(required_number_of_nodes):
      rank_base = (node * self.params.input.parallel_file_load.ranks_per_node)
      for rank in range(rank_base, rank_base + self.params.input.parallel_file_load.ranks_per_node):
        rank_files[rank] = node_files[node][rank - rank_base::self.params.input.parallel_file_load.ranks_per_node]
        if len(rank_files[rank]) > 0:
          required_number_of_ranks += 1

    if available_rank_count > 0: # if the caller has provided the available rank count, assert that we have enough ranks
      assert required_number_of_ranks <= available_rank_count, "Not enough ranks to load the reflection files: available %d rank(s), required %d rank(s)"%(available_rank_count, required_number_of_ranks)

    # optionally print out the anticipated memory load per node
    if debug:
      for node in range(required_number_of_nodes):
        anticipated_memory_usage_GB = 0
        for file_pair in node_files[node]:
          anticipated_memory_usage_GB += os.stat(file_pair[1]).st_size / b2GB * self.params.input.parallel_file_load.node_memory.pickle_to_memory
        self.debug_log_write("\nNode %d: anticipated memory usage %f GB"%(node, anticipated_memory_usage_GB))

    if debug:
      print ("File load calculator output file: ", self.debug_log_path)

    return rank_files

from xfel.merging.application.phil.phil import Script as Script_Base
class Script(Script_Base):
  '''A class for running the script.'''

  def get_file_list(self):
    '''Get experiments/reflections file list'''
    file_list = list_input_pairs(self.params)
    print("Built an input list of %d experiments/reflections file pairs"%len(file_list))
    print("To view the list, set debug=True in file_load_calculator.py")
    return file_list

  def run(self, available_rank_count=0):
    # Read and parse phil
    self.initialize()
    self.validate()

    # Calculate file load
    load_calculator = file_load_calculator(self.params, self.get_file_list())
    rank_files = load_calculator.calculate_file_load(available_rank_count)

    print ("OK")
    return

  def validate(self):
    """ Override to perform any validation of the input parameters """
    pass

if __name__ == '__main__':
  script = Script()
  result = script.run(available_rank_count)
  if result is None:
    sys.exit(1)
