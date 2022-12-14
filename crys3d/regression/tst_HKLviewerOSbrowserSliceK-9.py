from __future__ import absolute_import, division, print_function
from crys3d.regression import tests_HKLviewer


def run():
  tests_HKLviewer.exercise_OSbrowser(tests_HKLviewer.philstr1, tests_HKLviewer.reflections2match1,
                                    "OSbrowserSliceK-9" )
  print("OK")


if __name__ == '__main__':
  run()
