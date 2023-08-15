from __future__ import absolute_import, division, print_function
from libtbx import group_args

to_kcal_mol = {'ev':23.0609,
  }

def _print_energy_in_kcal(e, units):
  if units.lower() in to_kcal_mol:
    return '%15.3f %s' % (e*to_kcal_mol[units.lower()], 'kcal/mol')
  else:
    return '%15.3f %s' % (e, units)

def print_energy_in_kcal(ga):
  s=[]
  if ga is None: return s
  for d, e, l, b in ga.energies:
    units=ga.units.lower()
    if d in ['opt', 'bound']: atoms=b
    elif d in ['energy', 'strain']: atoms=l
    s.append('%-12s %s (atoms %4d)  ' % (d,
                                          _print_energy_in_kcal(e, units), atoms))
  return s

class energies(list):
  def __init__(self):
    pass

  def as_string(self, verbose=False):
    # from libtbx import easy_pickle
    # easy_pickle.dump('ga.pickle', self)
    pairs = [['bound', 'opt']]
    s=''
    tmp = {}
    t_atoms = {}
    for i, gas in enumerate(self):
      tmp.setdefault(i, {})
      t_atoms.setdefault(i, {})
      t=''
      units = None
      for j, ga in enumerate(gas):
        if ga:
          units=ga.units
          for d, e, l, b in ga.energies:
            tmp[i][d]=e
            t_atoms[i][d]=b
        rc = print_energy_in_kcal(ga)
        if rc:
          for line in rc:
            t += '%s%s\n' % (' '*6, line)
      if verbose: print('macro_cycle %d %s' % (i+1,t))
      for k1, k2 in pairs:
        if t_atoms[i][k1]!=t_atoms[i][k2]: continue
        if k1 in tmp[i] and k2 in tmp[i]:
          e = tmp[i][k1]-tmp[i][k2]
          t+='%s%-12s %s (atoms %4d)' % (' '*6,
                             '%s-%s' % (k1,k2),
                             _print_energy_in_kcal(e, units),
                             t_atoms[i][k1],
                             )
      if i:
        def _add_dE(e1, e2, units):
          s=''
          if e1 and e2:
            if e1[0]==e2[0]:
              if e1[0] in ['opt', 'bound']:
                b1=e1[3]==e2[3]
              if e1[0] in ['strain', 'energy']:
                b1=e1[2]==e2[2]
              if b1:
                de = e2[1]-e1[1]
                s+='%s%-12s %s\n' % (' '*6,
                                     '%s dE' % e2[0],
                                     _print_energy_in_kcal(e2[1]-e1[1],units))
          return s
        e1=e2=None
        for k in range(2):
          if gas[k] and first[k]:
            e2=gas[k].energies
            e1=first[k].energies
            for f1, f2 in zip(e1,e2):
              t+= _add_dE(f1,f2,gas[k].units)
              if verbose: print(i+1,f1,f2,s)
      else:
        first=gas
      if t:
        s+='%sMacro cycle %d\n' % (' '*4, i+1)
        s+=t
    return s

class all_energies(dict):
  def __init__(self):
    pass

  def as_string(self):
    s='QM energies\n'
    for selection, energies in self.items():
      s+='\n  "%s"\n' % selection
      s+='%s' % energies.as_string()
    return s

def digest_return_energy_object(ga, macro_cycle, energy_only, rc=None):
  if rc is None:
    rc = all_energies()
  if ga is None: return rc
  for selection, es in ga.energies.items():
    rc.setdefault(selection, energies())
    while len(rc[selection])<macro_cycle:
      rc[selection].append([None,None,None])
    if energy_only:
      rc[selection][-1][0]=group_args(energies=es,
                                      units=ga.units,
                                      )
    else:
      rc[selection][-1][1]=group_args(energies=es,
                                      units=ga.units,
                                      )
  return rc

if __name__ == '__main__':
  from libtbx import easy_pickle
  e=easy_pickle.load('ga.pickle')
  rc=e.as_string(verbose=0)
  print(rc)
