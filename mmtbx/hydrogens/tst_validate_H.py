from __future__ import division
import time
import mmtbx.model
import iotbx.pdb
from mmtbx.monomer_library.pdb_interpretation import grand_master_phil_str
from libtbx.test_utils import approx_equal
from mmtbx.hydrogens.validate_H import validate_H
#from validate_H_cl_app import master_params_str

pdb_str = """
CRYST1   31.264   27.900   96.292  90.00  90.00  90.00 P 1
SCALE1      0.031986  0.000000  0.000000        0.00000
SCALE2      0.000000  0.035842  0.000000        0.00000
SCALE3      0.000000  0.000000  0.010385        0.00000
ATOM      1  N   ASN A   1      25.174 -24.761 -21.940  1.00 16.59           N
ATOM      2  CA  ASN A   1      25.971 -25.578 -22.850  1.00 17.25           C
ATOM      3  C   ASN A   1      26.037 -24.941 -24.225  1.00 16.66           C
ATOM      4  O   ASN A   1      27.077 -24.979 -24.874  1.00 18.42           O
ATOM      5  CB  ASN A   1      25.498 -27.040 -22.913  1.00 18.30           C
ATOM      6  CG  ASN A   1      24.187 -27.208 -23.672  1.00 20.42           C
ATOM      7  OD1 ASN A   1      23.167 -26.590 -23.335  1.00 20.87           O
ATOM      8  ND2 ASN A   1      24.200 -28.069 -24.685  1.00 18.15           N
ATOM      9  DA  ASN A   1      26.975 -25.581 -22.461  1.00 15.99           D
ATOM     10 DD21 ASN A   1      25.030 -28.545 -24.882  1.00 16.07           D
ATOM     11  D  AASN A   1      24.379 -25.105 -21.517  0.82 16.71           D
ATOM     12  DB2AASN A   1      25.358 -27.400 -21.898  0.65 18.82           D
ATOM     13  DB3AASN A   1      26.255 -27.641 -23.402  0.56 18.30           D
ATOM     14 DD22AASN A   1      23.370 -28.163 -25.192  0.72 16.98           D
ATOM     15  H  BASN A   1      24.379 -25.105 -21.517  0.18 16.71           H
ATOM     16  HB2BASN A   1      26.255 -27.641 -23.402  0.44 18.30           H
ATOM     17  HB3BASN A   1      25.358 -27.400 -21.898  0.35 18.82           H
ATOM     18 HD22BASN A   1      23.370 -28.163 -25.192  0.28 16.98           H
ATOM     19  N   ASN A   2      23.615 -22.281 -25.492  1.00 16.59           N
ATOM     20  CA  ASN A   2      24.412 -23.098 -26.402  1.00 17.25           C
ATOM     21  C   ASN A   2      24.478 -22.461 -27.777  1.00 16.66           C
ATOM     22  O   ASN A   2      25.518 -22.499 -28.426  1.00 18.42           O
ATOM     23  CB  ASN A   2      23.939 -24.560 -26.465  1.00 18.30           C
ATOM     24  CG  ASN A   2      22.628 -24.728 -27.224  1.00 20.42           C
ATOM     25  OD1 ASN A   2      21.608 -24.110 -26.887  1.00 20.87           O
ATOM     26  ND2 ASN A   2      22.641 -25.589 -28.237  1.00 18.15           N
ATOM     27  DA  ASN A   2      25.416 -23.101 -26.013  1.00 15.99           D
ATOM     28 HD21 ASN A   2      23.471 -26.065 -28.434  1.00 16.07           H
ATOM     29  D  AASN A   2      22.820 -22.625 -25.069  0.82 16.71           D
ATOM     30  DB2AASN A   2      23.799 -24.920 -25.450  0.65 18.82           D
ATOM     31  DB3AASN A   2      24.696 -25.161 -26.954  0.56 18.30           D
ATOM     32 DD22AASN A   2      21.811 -25.683 -28.744  0.72 16.98           D
ATOM     33  H  BASN A   2      22.820 -22.625 -25.069  0.18 16.71           H
ATOM     34  HB2BASN A   2      24.696 -25.161 -26.954  0.44 18.30           H
ATOM     35  HB3BASN A   2      23.799 -24.920 -25.450  0.35 18.82           H
ATOM     36 HD22BASN A   2      21.811 -25.683 -28.744  0.28 16.98           H
ATOM     37  N   LEU A   3      23.374 -21.865 -28.222  1.00 15.90           N
ATOM     38  CA  LEU A   3      23.342 -21.224 -29.530  1.00 15.47           C
ATOM     39  C   LEU A   3      23.637 -19.727 -29.491  1.00 18.18           C
ATOM     40  O   LEU A   3      24.174 -19.175 -30.462  1.00 20.24           O
ATOM     41  CB  LEU A   3      22.021 -21.521 -30.238  1.00 15.76           C
ATOM     42  CG  LEU A   3      21.790 -23.005 -30.533  1.00 19.30           C
ATOM     43  CD1 LEU A   3      20.460 -23.197 -31.290  1.00 20.74           C
ATOM     44  CD2 LEU A   3      22.957 -23.627 -31.336  1.00 17.02           C
ATOM     45  DA  LEU A   3      24.132 -21.653 -30.101  1.00 12.76           D
ATOM     46  DB3 LEU A   3      21.233 -21.196 -29.610  1.00 17.93           D
ATOM     47  D  ALEU A   3      22.567 -21.865 -27.663  0.91 16.63           D
ATOM     48  DB2ALEU A   3      21.964 -20.976 -31.155  0.67 16.51           D
ATOM     49  DG ALEU A   3      21.719 -23.530 -29.581  0.68 18.31           D
ATOM     50 DD11ALEU A   3      19.620 -22.925 -30.652  0.74 20.52           D
ATOM     51 DD12ALEU A   3      20.364 -24.239 -31.597  0.77 19.78           D
ATOM     52 DD13ALEU A   3      20.458 -22.568 -32.171  0.49 20.26           D
ATOM     53 DD21ALEU A   3      23.466 -22.855 -31.890  0.40 16.87           D
ATOM     54 DD22ALEU A   3      22.563 -24.357 -32.028  0.00 16.68           D
ATOM     55 DD23ALEU A   3      23.653 -24.109 -30.673  0.89 14.39           D
ATOM     56  H  BLEU A   3      22.567 -21.865 -27.663  0.09 16.63           H
ATOM     57  HB2BLEU A   3      21.964 -20.976 -31.155  0.33 14.51           H
ATOM     58  HG BLEU A   3      21.719 -23.530 -29.581  0.32 18.31           H
ATOM     59 HD11BLEU A   3      19.620 -22.925 -30.652  0.26 20.52           H
ATOM     60 HD12BLEU A   3      20.364 -24.239 -31.597  0.23 19.78           H
ATOM     61 HD13BLEU A   3      20.458 -22.568 -32.171  0.51 20.26           H
ATOM     62 HD21BLEU A   3      23.466 -22.855 -31.890  0.60 16.87           H
ATOM     63 HD22BLEU A   3      22.563 -24.357 -32.028  0.58 16.68           H
ATOM     64 HD23BLEU A   3      23.653 -24.109 -30.673  0.11 14.39           H
ATOM     65  N   SER A   4       9.243 -32.509 -36.471  1.00 38.02           N
ATOM     66  CA  SER A   4      10.063 -33.604 -36.981  1.00 39.55           C
ATOM     67  C   SER A   4      11.459 -33.153 -37.367  1.00 37.45           C
ATOM     68  O   SER A   4      11.633 -32.304 -38.239  1.00 38.82           O
ATOM     69  CB  SER A   4       9.384 -34.279 -38.180  1.00 41.66           C
ATOM     70  OG  SER A   4       8.375 -35.181 -37.753  1.00 44.91           O
ATOM     71  DA  SER A   4      10.165 -34.324 -36.187  1.00 38.72           D
ATOM     72  D  ASER A   4       8.730 -31.950 -37.103  0.62 38.48           D
ATOM     73  DB2ASER A   4      10.116 -34.818 -38.774  0.63 41.36           D
ATOM     74  DB3ASER A   4       8.918 -33.518 -38.793  0.36 41.73           D
ATOM     75  DG ASER A   4       8.699 -36.084 -37.842  0.36 43.61           D
ATOM     76  H  BSER A   4       8.730 -31.950 -37.103  0.28 38.48           H
ATOM     77  HB2BSER A   4       8.918 -33.518 -38.793  0.64 41.73           H
ATOM     78  HB3BSER A   4      10.116 -34.818 -38.774  0.37 41.36           H
ATOM     79  HG BSER A   4       8.699 -36.084 -37.842  0.64 43.61           H
ATOM     80  N   SER A   5      26.478 -19.398  45.776  1.00 19.78           N
ATOM     81  C   SER A   5      27.940 -19.562  43.818  1.00 21.99           C
ATOM     82  O   SER A   5      29.005 -19.770  43.306  1.00 21.20           O
ATOM     83  CA ASER A   5      27.849 -19.441  45.318  0.64 18.99           C
ATOM     84  CB ASER A   5      28.611 -20.590  45.987  0.64 21.66           C
ATOM     85  OG ASER A   5      28.819 -20.337  47.363  0.64 23.21           O
ATOM     86  DG ASER A   5      29.639 -20.155  47.499  0.64 22.10           D
ATOM     87  H  ASER A   5      26.064 -20.150  45.742  0.06 18.55           H
ATOM     88  HA ASER A   5      28.296 -18.610  45.561  0.64 20.89           H
ATOM     89  HB2ASER A   5      28.094 -21.408  45.903  0.00 22.17           H
ATOM     90  HB3ASER A   5      29.468 -20.686  45.544  0.64 22.38           H
ATOM     91  CA BSER A   5      27.851 -19.476  45.322  0.36 19.02           C
ATOM     92  CB BSER A   5      28.561 -20.680  45.932  0.36 21.98           C
ATOM     93  OG BSER A   5      28.005 -21.879  45.425  0.36 25.40           O
ATOM     94  D  BSER A   5      26.023 -20.128  45.688  0.94 18.55           D
ATOM     95  HA BSER A   5      28.327 -18.675  45.599  0.36 21.03           H
ATOM     96  HB2BSER A   5      29.498 -20.638  45.691  0.36 22.55           H
ATOM     97  HB3BSER A   5      28.462 -20.665  46.898  0.36 23.83           H
ATOM     98  HG BSER A   5      27.486 -22.196  46.000  0.36 22.10           H
TER
HETATM   99  O   HOH B   1      25.202 -21.329 -23.306  1.00 30.00           O
HETATM  100  D1  HOH B   1      25.963 -20.763 -23.255  1.00 30.00           D
HETATM  101  D2  HOH B   1      24.439 -20.764 -23.305  1.00 30.00           D
HETATM  102  O   HOH B   2      26.442 -21.454 -25.349  1.00 30.00           O
HETATM  103  D1  HOH B   2      27.249 -20.953 -25.339  1.00 30.00           D
HETATM  104  O   HOH B   3      24.970 -18.184 -24.460  1.00 30.00           O
HETATM  105  O   HOH B   4      21.573 -23.174 -24.023  1.00 30.00           O
HETATM  106  D2  HOH B   4      20.731 -22.736 -24.071  1.00 30.00           D
HETATM  107  D1 AHOH B   4      22.045 -22.784 -23.297  1.00 30.00           D
HETATM  108  D1 BHOH B   4      22.145 -21.784 -22.297  1.00 30.00           D
HETATM  109  D1  HOH B   5      21.772 -27.767 -28.880  1.00 30.00           D
TER
END
"""

# exercise1 a) The C beta DB2 and DB3 atoms are swapped
pdb_str1a = """
CRYST1   17.955   13.272   13.095  90.00  90.00  90.00 P 1
SCALE1      0.055695  0.000000  0.000000        0.00000
SCALE2      0.000000  0.075347  0.000000        0.00000
SCALE3      0.000000  0.000000  0.076365        0.00000
ATOM      1  N   TYR A 139      10.241   7.920   5.000  1.00 10.00           N
ATOM      2  CA  TYR A 139      10.853   7.555   6.271  1.00 10.00           C
ATOM      3  C   TYR A 139      12.362   7.771   6.227  1.00 10.00           C
ATOM      4  O   TYR A 139      12.955   8.272   7.181  1.00 10.00           O
ATOM      5  CB  TYR A 139      10.540   6.098   6.617  1.00 10.00           C
ATOM      6  CG  TYR A 139       9.063   5.805   6.749  1.00 10.00           C
ATOM      7  CD1 TYR A 139       8.316   5.391   5.654  1.00 10.00           C
ATOM      8  CD2 TYR A 139       8.414   5.943   7.969  1.00 10.00           C
ATOM      9  CE1 TYR A 139       6.966   5.122   5.770  1.00 10.00           C
ATOM     10  CE2 TYR A 139       7.064   5.676   8.095  1.00 10.00           C
ATOM     11  CZ  TYR A 139       6.345   5.266   6.993  1.00 10.00           C
ATOM     12  OH  TYR A 139       5.000   5.000   7.113  1.00 10.00           O
ATOM     13  HA ATYR A 139      10.443   8.186   7.059  0.50 10.00           H
ATOM     14  HB2ATYR A 139      10.938   5.457   5.830  0.50 10.00           H
ATOM     15  HB3ATYR A 139      11.014   5.853   7.567  0.50 10.00           H
ATOM     16  HD1ATYR A 139       8.799   5.277   4.695  0.50 10.00           H
ATOM     17  HD2ATYR A 139       8.974   6.264   8.835  0.50 10.00           H
ATOM     18  HE1ATYR A 139       6.400   4.801   4.908  0.50 10.00           H
ATOM     19  HE2ATYR A 139       6.575   5.788   9.051  0.50 10.00           H
ATOM     20  HH ATYR A 139       4.710   5.148   8.037  0.50 10.00           H
ATOM     21  DA BTYR A 139      10.443   8.186   7.059  0.50 10.00           D
ATOM     22  DB3BTYR A 139      10.938   5.457   5.830  0.50 10.00           D
ATOM     23  DB2BTYR A 139      11.014   5.853   7.567  0.50 10.00           D
ATOM     24  DD1BTYR A 139       8.799   5.277   4.695  0.50 10.00           D
ATOM     25  DD2BTYR A 139       8.974   6.264   8.835  0.50 10.00           D
ATOM     26  DE1BTYR A 139       6.400   4.801   4.908  0.50 10.00           D
ATOM     27  DE2BTYR A 139       6.575   5.788   9.051  0.50 10.00           D
ATOM     28  DH BTYR A 139       4.710   5.148   8.037  0.50 10.00           D
"""

# exercise1 b) The C beta HB2 and HB3 atoms are swapped
pdb_str1b = """
CRYST1   17.955   13.272   13.095  90.00  90.00  90.00 P 1
SCALE1      0.055695  0.000000  0.000000        0.00000
SCALE2      0.000000  0.075347  0.000000        0.00000
SCALE3      0.000000  0.000000  0.076365        0.00000
ATOM      1  N   TYR A 139      10.241   7.920   5.000  1.00 10.00           N
ATOM      2  CA  TYR A 139      10.853   7.555   6.271  1.00 10.00           C
ATOM      3  C   TYR A 139      12.362   7.771   6.227  1.00 10.00           C
ATOM      4  O   TYR A 139      12.955   8.272   7.181  1.00 10.00           O
ATOM      5  CB  TYR A 139      10.540   6.098   6.617  1.00 10.00           C
ATOM      6  CG  TYR A 139       9.063   5.805   6.749  1.00 10.00           C
ATOM      7  CD1 TYR A 139       8.316   5.391   5.654  1.00 10.00           C
ATOM      8  CD2 TYR A 139       8.414   5.943   7.969  1.00 10.00           C
ATOM      9  CE1 TYR A 139       6.966   5.122   5.770  1.00 10.00           C
ATOM     10  CE2 TYR A 139       7.064   5.676   8.095  1.00 10.00           C
ATOM     11  CZ  TYR A 139       6.345   5.266   6.993  1.00 10.00           C
ATOM     12  OH  TYR A 139       5.000   5.000   7.113  1.00 10.00           O
ATOM     13  HA ATYR A 139      10.443   8.186   7.059  0.50 10.00           H
ATOM     14  HB3ATYR A 139      10.938   5.457   5.830  0.50 10.00           H
ATOM     15  HB2ATYR A 139      11.014   5.853   7.567  0.50 10.00           H
ATOM     16  HD1ATYR A 139       8.799   5.277   4.695  0.50 10.00           H
ATOM     17  HD2ATYR A 139       8.974   6.264   8.835  0.50 10.00           H
ATOM     18  HE1ATYR A 139       6.400   4.801   4.908  0.50 10.00           H
ATOM     19  HE2ATYR A 139       6.575   5.788   9.051  0.50 10.00           H
ATOM     20  HH ATYR A 139       4.710   5.148   8.037  0.50 10.00           H
ATOM     21  DA BTYR A 139      10.443   8.186   7.059  0.50 10.00           D
ATOM     22  DB2BTYR A 139      10.938   5.457   5.830  0.50 10.00           D
ATOM     23  DB3BTYR A 139      11.014   5.853   7.567  0.50 10.00           D
ATOM     24  DD1BTYR A 139       8.799   5.277   4.695  0.50 10.00           D
ATOM     25  DD2BTYR A 139       8.974   6.264   8.835  0.50 10.00           D
ATOM     26  DE1BTYR A 139       6.400   4.801   4.908  0.50 10.00           D
ATOM     27  DE2BTYR A 139       6.575   5.788   9.051  0.50 10.00           D
ATOM     28  DH BTYR A 139       4.710   5.148   8.037  0.50 10.00           D
"""

pdb_str2 = """
CRYST1   17.955   13.272   13.095  90.00  90.00  90.00 P 1
SCALE1      0.055695  0.000000  0.000000        0.00000
SCALE2      0.000000  0.075347  0.000000        0.00000
SCALE3      0.000000  0.000000  0.076365        0.00000
ATOM      1  N   TYR A 139      10.241   7.920   5.000  1.00 10.00           N
ATOM      2  CA  TYR A 139      10.853   7.555   6.271  1.00 10.00           C
ATOM      3  C   TYR A 139      12.362   7.771   6.227  1.00 10.00           C
ATOM      4  O   TYR A 139      12.955   8.272   7.181  1.00 10.00           O
ATOM      5  CB  TYR A 139      10.540   6.098   6.617  1.00 10.00           C
ATOM      6  CG  TYR A 139       9.063   5.805   6.749  1.00 10.00           C
ATOM      7  CD1 TYR A 139       8.316   5.391   5.654  1.00 10.00           C
ATOM      8  CD2 TYR A 139       8.414   5.943   7.969  1.00 10.00           C
ATOM      9  CE1 TYR A 139       6.966   5.122   5.770  1.00 10.00           C
ATOM     10  CE2 TYR A 139       7.064   5.676   8.095  1.00 10.00           C
ATOM     11  CZ  TYR A 139       6.345   5.266   6.993  1.00 10.00           C
ATOM     12  OH  TYR A 139       5.000   5.000   7.113  1.00 10.00           O
ATOM     13  HA ATYR A 139      10.443   8.186   7.059  0.50 10.00           H
ATOM     14  HB2ATYR A 139      10.938   5.457   5.830  0.50 10.00           H
ATOM     15  HB3ATYR A 139      11.014   5.853   7.567  0.50 10.00           H
ATOM     16  HD1ATYR A 139       8.799   5.277   4.695  0.50  8.00           H
ATOM     17  HD2ATYR A 139       8.974   6.264   8.835  0.50 10.00           H
ATOM     18  HE1ATYR A 139       6.400   4.801   4.908  0.50 10.00           H
ATOM     19  HE2ATYR A 139       6.575   5.788   9.051  0.50 10.00           H
ATOM     20  HH ATYR A 139       4.564   5.706   7.633  0.60 10.00           H
ATOM     21  DA BTYR A 139      10.543   8.286   7.059  0.50 10.00           D
ATOM     22  DB2BTYR A 139      10.938   5.457   5.830  0.50 10.00           D
ATOM     23  DB3BTYR A 139      11.014   5.853   7.567  0.50 10.00           D
ATOM     24  DD1BTYR A 139       8.799   5.277   4.695  0.50 10.00           D
ATOM     25  DD2BTYR A 139       8.974   6.264   8.835  0.50 10.00           D
ATOM     26  DE1BTYR A 139       6.400   4.801   4.908  0.50 10.00           D
ATOM     27  DE2BTYR A 139       6.575   5.788   9.051  0.50 10.00           D
ATOM     28  DH BTYR A 139       4.710   5.148   8.037  0.40 10.00           D
"""

pdb_str3 = """
CRYST1   17.955   13.272   13.095  90.00  90.00  90.00 P 1
SCALE1      0.055695  0.000000  0.000000        0.00000
SCALE2      0.000000  0.075347  0.000000        0.00000
SCALE3      0.000000  0.000000  0.076365        0.00000
ATOM      1  N   TYR A 139      10.241   7.920   5.000  1.00 10.00           N
ATOM      2  CA  TYR A 139      10.853   7.555   6.271  1.00 10.00           C
ATOM      3  C   TYR A 139      12.362   7.771   6.227  1.00 10.00           C
ATOM      4  O   TYR A 139      12.955   8.272   7.181  1.00 10.00           O
ATOM      5  CB  TYR A 139      10.540   6.098   6.617  1.00 10.00           C
ATOM      6  CG  TYR A 139       9.063   5.805   6.749  1.00 10.00           C
ATOM      7  CD1 TYR A 139       8.316   5.391   5.654  1.00 10.00           C
ATOM      8  CD2 TYR A 139       8.414   5.943   7.969  1.00 10.00           C
ATOM      9  CE1 TYR A 139       6.966   5.122   5.770  1.00 10.00           C
ATOM     10  CE2 TYR A 139       7.064   5.676   8.095  1.00 10.00           C
ATOM     11  CZ  TYR A 139       6.345   5.266   6.993  1.00 10.00           C
ATOM     12  OH  TYR A 139       5.000   5.000   7.113  1.00 10.00           O
ATOM     13  HA ATYR A 139      10.443   8.186   7.059  0.50 10.00           H
ATOM     14  HB2ATYR A 139      10.938   5.457   5.830  0.00 10.00           H
ATOM     15  HB3ATYR A 139      11.014   5.853   7.567  0.50 10.00           H
ATOM     16  HD1 TYR A 139       8.799   5.277   4.695  0.50 10.00           H
ATOM     17  HD2ATYR A 139       8.974   6.264   8.835  0.40 10.00           H
ATOM     18  HE1ATYR A 139       6.400   4.801   4.908  0.50 10.00           H
ATOM     19  HE2ATYR A 139       6.575   5.788   9.051  0.50 10.00           H
ATOM     20  HH ATYR A 139       4.710   5.148   8.037  0.50 10.00           H
ATOM     21  DA BTYR A 139      10.443   8.186   7.059  0.50 10.00           D
ATOM     22  DB2BTYR A 139      10.938   5.457   5.830  1.00 10.00           D
ATOM     23  DB3BTYR A 139      11.014   5.853   7.567  0.50 10.00           D
ATOM     25  DD2BTYR A 139       8.974   6.264   8.835  0.50 10.00           D
ATOM     26  DE1BTYR A 139       6.400   4.801   4.908  0.50 10.00           D
ATOM     27  DE2BTYR A 139       6.575   5.788   9.051  0.60 10.00           D
ATOM     28  DH BTYR A 139       4.710   5.148   8.037  0.50 10.00           D
"""

pdb_str4 = """
CRYST1   17.955   13.272   13.095  90.00  90.00  90.00 P 1
SCALE1      0.055695  0.000000  0.000000        0.00000
SCALE2      0.000000  0.075347  0.000000        0.00000
SCALE3      0.000000  0.000000  0.076365        0.00000
ATOM      1  N   TYR A 139      10.241   7.920   5.000  1.00 10.00           N
ATOM      2  CA  TYR A 139      10.853   7.555   6.271  1.00 10.00           C
ATOM      3  C   TYR A 139      12.362   7.771   6.227  1.00 10.00           C
ATOM      4  O   TYR A 139      12.955   8.272   7.181  1.00 10.00           O
ATOM      5  CB  TYR A 139      10.540   6.098   6.617  1.00 10.00           C
ATOM      6  CG  TYR A 139       9.063   5.805   6.749  1.00 10.00           C
ATOM      7  CD1 TYR A 139       8.316   5.391   5.654  1.00 10.00           C
ATOM      8  CD2 TYR A 139       8.414   5.943   7.969  1.00 10.00           C
ATOM      9  CE1 TYR A 139       6.966   5.122   5.770  1.00 10.00           C
ATOM     10  CE2 TYR A 139       7.064   5.676   8.095  1.00 10.00           C
ATOM     11  CZ  TYR A 139       6.345   5.266   6.993  1.00 10.00           C
ATOM     12  OH  TYR A 139       5.000   5.000   7.113  1.00 10.00           O
ATOM     13  HA  TYR A 139      10.443   8.186   7.059  1.00 10.00           H
ATOM     15  HB3 TYR A 139      11.014   5.853   7.567  1.00 10.00           H
ATOM     16  HD1 TYR A 139       8.799   5.277   4.695  1.00 10.00           H
ATOM     17  HD2 TYR A 139       8.974   6.264   8.835  1.00 10.00           H
ATOM     19  HE2 TYR A 139       6.575   5.788   9.051  1.00 10.00           H
ATOM     20  HH  TYR A 139       4.710   5.148   8.037  1.00 10.00           H
"""

pdb_str5 = """
CRYST1   17.955   13.272   13.095  90.00  90.00  90.00 P 1
SCALE1      0.055695  0.000000  0.000000        0.00000
SCALE2      0.000000  0.075347  0.000000        0.00000
SCALE3      0.000000  0.000000  0.076365        0.00000
ATOM      1  N   TYR A 139      10.241   7.920   5.000  1.00 10.00           N
ATOM      2  CA  TYR A 139      10.853   7.555   6.271  1.00 10.00           C
ATOM      3  C   TYR A 139      12.362   7.771   6.227  1.00 10.00           C
ATOM      4  O   TYR A 139      12.955   8.272   7.181  1.00 10.00           O
ATOM      5  CB  TYR A 139      10.540   6.098   6.617  1.00 10.00           C
ATOM      6  CG  TYR A 139       9.063   5.805   6.749  1.00 10.00           C
ATOM      7  CD1 TYR A 139       8.316   5.391   5.654  1.00 10.00           C
ATOM      8  CD2 TYR A 139       8.414   5.943   7.969  1.00 10.00           C
ATOM      9  CE1 TYR A 139       6.966   5.122   5.770  1.00 10.00           C
ATOM     10  CE2 TYR A 139       7.064   5.676   8.095  1.00 10.00           C
ATOM     11  CZ  TYR A 139       6.345   5.266   6.993  1.00 10.00           C
ATOM     12  OH  TYR A 139       5.000   5.000   7.113  1.00 10.00           O
ATOM     13  DA  TYR A 139      10.443   8.186   7.059  1.00 10.00           D
ATOM     15  DB3 TYR A 139      11.014   5.853   7.567  1.00 10.00           D
ATOM     16  DD1 TYR A 139       8.799   5.277   4.695  1.00 10.00           D
ATOM     17  DD2 TYR A 139       8.974   6.264   8.835  1.00 10.00           D
ATOM     19  DE2 TYR A 139       6.575   5.788   9.051  1.00 10.00           D
ATOM     20  DH  TYR A 139       4.710   5.148   8.037  1.00 10.00           D
"""

pdb_str6 = """
CRYST1   17.955   13.272   13.095  90.00  90.00  90.00 P 1
SCALE1      0.055695  0.000000  0.000000        0.00000
SCALE2      0.000000  0.075347  0.000000        0.00000
SCALE3      0.000000  0.000000  0.076365        0.00000
ATOM      1  N   TYR A 139      10.241   7.920   5.000  1.00 10.00           N
ATOM      2  CA  TYR A 139      10.853   7.555   6.271  1.00 10.00           C
ATOM      3  C   TYR A 139      12.362   7.771   6.227  1.00 10.00           C
ATOM      4  O   TYR A 139      12.955   8.272   7.181  1.00 10.00           O
ATOM      5  CB  TYR A 139      10.540   6.098   6.617  1.00 10.00           C
ATOM      7  CD1 TYR A 139       8.316   5.391   5.654  1.00 10.00           C
ATOM      8  CD2 TYR A 139       8.414   5.943   7.969  1.00 10.00           C
ATOM      9  CE1 TYR A 139       6.966   5.122   5.770  1.00 10.00           C
ATOM     10  CE2 TYR A 139       7.064   5.676   8.095  1.00 10.00           C
ATOM     11  CZ  TYR A 139       6.345   5.266   6.993  1.00 10.00           C
ATOM     12  OH  TYR A 139       5.000   5.000   7.113  1.00 10.00           O
ATOM     13  HA ATYR A 139      10.443   8.186   7.059  0.50 10.00           H
ATOM     14  HB2ATYR A 139      10.938   5.457   5.830  0.50 10.00           H
ATOM     15  HB3ATYR A 139      11.014   5.853   7.567  0.50 10.00           H
ATOM     16  HD1ATYR A 139       8.799   5.277   4.695  0.50 10.00           H
ATOM     19  HE2ATYR A 139       6.575   5.788   9.051  0.50 10.00           H
ATOM     20  HH  TYR A 139       4.710   5.148   8.037  1.00 10.00           H
ATOM     21  DA BTYR A 139      10.443   8.186   7.059  0.50 10.00           D
ATOM     22  DB2BTYR A 139      10.938   5.457   5.830  0.50 10.00           D
ATOM     24  DD1BTYR A 139       8.799   5.277   4.695  0.50 10.00           D
ATOM     26  DE1BTYR A 139       6.400   4.801   4.908  0.50 10.00           D
ATOM     27  DE2BTYR A 139       6.575   5.788   9.051  0.50 10.00           D
"""

pdb_str7 = """
CRYST1   17.955   13.272   13.095  90.00  90.00  90.00 P 1
SCALE1      0.055695  0.000000  0.000000        0.00000
SCALE2      0.000000  0.075347  0.000000        0.00000
SCALE3      0.000000  0.000000  0.076365        0.00000
ATOM      1  N   TYR A 139      10.241   7.920   5.000  1.00 10.00           N
ATOM      2  CA  TYR A 139      10.853   7.555   6.271  1.00 10.00           C
ATOM      3  C   TYR A 139      12.362   7.771   6.227  1.00 10.00           C
ATOM      4  O   TYR A 139      12.955   8.272   7.181  1.00 10.00           O
ATOM      5  CB  TYR A 139      10.540   6.098   6.617  1.00 10.00           C
ATOM      6  CG  TYR A 139       9.063   5.805   6.749  1.00 10.00           C
ATOM      7  CD1 TYR A 139       8.316   5.391   5.654  1.00 10.00           C
ATOM      8  CD2 TYR A 139       8.414   5.943   7.969  1.00 10.00           C
ATOM      9  CE1 TYR A 139       6.966   5.122   5.770  1.00 10.00           C
ATOM     10  CE2 TYR A 139       7.064   5.676   8.095  1.00 10.00           C
ATOM     11  CZ  TYR A 139       6.345   5.266   6.993  1.00 10.00           C
ATOM     12  OH  TYR A 139       5.000   5.000   7.113  1.00 10.00           O
ATOM     13  HA ATYR A 139      10.443   8.186   7.059  0.50 10.00           H
ATOM     14  HB2ATYR A 139      11.057   5.645   5.981  0.50 10.00           H
ATOM     15  HB3ATYR A 139      10.870   5.954   7.475  0.50 10.00           H
ATOM     16  HD1ATYR A 139       8.799   5.277   4.695  0.50 10.00           H
ATOM     17  HD2ATYR A 139       8.792   6.377   9.033  0.50 10.00           H
ATOM     18  HE1ATYR A 139       6.400   4.801   4.908  0.50 10.00           H
ATOM     19  HE2ATYR A 139       6.575   5.788   9.051  0.50 10.00           H
ATOM     20  HH ATYR A 139       4.837   5.050   7.863  0.50 10.00           H
"""

pdb_str8 = """
CRYST1   17.955   13.272   13.095  90.00  90.00  90.00 P 1
SCALE1      0.055695  0.000000  0.000000        0.00000
SCALE2      0.000000  0.075347  0.000000        0.00000
SCALE3      0.000000  0.000000  0.076365        0.00000
ATOM      1  N   TYR A 139      10.241   7.920   5.000  1.00 10.00           N
ATOM      2  CA  TYR A 139      10.853   7.555   6.271  1.00 10.00           C
ATOM      3  C   TYR A 139      12.362   7.771   6.227  1.00 10.00           C
ATOM      4  O   TYR A 139      12.955   8.272   7.181  1.00 10.00           O
ATOM      5  CB  TYR A 139      10.540   6.098   6.617  1.00 10.00           C
ATOM      6  CG  TYR A 139       9.063   5.805   6.749  1.00 10.00           C
ATOM      7  CD1 TYR A 139       8.316   5.391   5.654  1.00 10.00           C
ATOM      8  CD2 TYR A 139       8.414   5.943   7.969  1.00 10.00           C
ATOM      9  CE1 TYR A 139       6.966   5.122   5.770  1.00 10.00           C
ATOM     10  CE2 TYR A 139       7.064   5.676   8.095  1.00 10.00           C
ATOM     11  CZ  TYR A 139       6.345   5.266   6.993  1.00 10.00           C
ATOM     12  OH  TYR A 139       5.000   5.000   7.113  1.00 10.00           O
ATOM     21  DA  TYR A 139      10.443   8.186   7.059  1.00 10.00           D
ATOM     14  DB2 TYR A 139      10.783   5.595   5.785  1.00 10.00           D
ATOM     15  DB3 TYR A 139      11.112   5.843   7.715  1.00 10.00           D
ATOM     16  DD1 TYR A 139       8.781   5.167   4.530  1.00 10.00           D
ATOM     25  DD2 TYR A 139       8.974   6.264   8.835  1.00 10.00           D
ATOM     26  DE1 TYR A 139       6.400   4.801   4.908  1.00 10.00           D
ATOM     19  DE2 TYR A 139       6.754   5.829   8.900  1.00 10.00           D
ATOM     28  DH  TYR A 139       4.710   5.148   8.037  1.00 10.00           D
"""

pdb_str9 = """
CRYST1   17.955   13.272   13.095  90.00  90.00  90.00 P 1
SCALE1      0.055695  0.000000  0.000000        0.00000
SCALE2      0.000000  0.075347  0.000000        0.00000
SCALE3      0.000000  0.000000  0.076365        0.00000
ATOM      1  N   TYR A 139      10.241   7.920   5.000  1.00 10.00           N
ATOM      2  CA  TYR A 139      10.853   7.555   6.271  1.00 10.00           C
ATOM      3  C   TYR A 139      12.362   7.771   6.227  1.00 10.00           C
ATOM      4  O   TYR A 139      12.955   8.272   7.181  1.00 10.00           O
ATOM      5  CB  TYR A 139      10.540   6.098   6.617  1.00 10.00           C
ATOM      6  CG  TYR A 139       9.063   5.805   6.749  1.00 10.00           C
ATOM      7  CD1 TYR A 139       8.316   5.391   5.654  1.00 10.00           C
ATOM      8  CD2 TYR A 139       8.414   5.943   7.969  1.00 10.00           C
ATOM      9  CE1 TYR A 139       6.966   5.122   5.770  1.00 10.00           C
ATOM     10  CE2 TYR A 139       7.064   5.676   8.095  1.00 10.00           C
ATOM     11  CZ  TYR A 139       6.345   5.266   6.993  1.00 10.00           C
ATOM     12  OH  TYR A 139       5.000   5.000   7.113  1.00 10.00           O
ATOM     13  HA ATYR A 139      10.443   8.186   7.059  0.50 10.00           H
ATOM     14  HB2ATYR A 139      10.968   5.639   5.981  0.50 10.00           H
ATOM     15  HB3ATYR A 139      11.014   5.853   7.567  0.50 10.00           H
ATOM     16  HD1ATYR A 139       8.799   5.277   4.695  0.50 10.00           H
ATOM     17  HD2ATYR A 139       8.974   6.264   8.835  0.50 10.00           H
ATOM     18  HE1ATYR A 139       6.400   4.801   4.908  0.50 10.00           H
ATOM     19  HE2ATYR A 139       6.648   5.677   8.989  0.50 10.00           H
ATOM     20  HH ATYR A 139       4.710   5.148   8.037  0.50 10.00           H
ATOM     21  DA BTYR A 139      10.443   8.186   7.059  0.50 10.00           D
ATOM     22  DB2BTYR A 139      10.938   5.457   5.830  0.50 10.00           D
ATOM     23  DB3BTYR A 139      11.014   5.853   7.567  0.50 10.00           D
ATOM     24  DD1BTYR A 139       8.832   5.349   4.523  0.50 10.00           D
ATOM     25  DD2BTYR A 139       8.974   6.264   8.835  0.50 10.00           D
ATOM     26  DE1BTYR A 139       6.400   4.801   4.908  0.50 10.00           D
ATOM     27  DE2BTYR A 139       6.575   5.788   9.051  0.50 10.00           D
ATOM     28  DH BTYR A 139       4.823   5.165   8.210  0.50 10.00           D
"""

pdb_str10 = """
CRYST1   17.955   13.272   13.095  90.00  90.00  90.00 P 1
SCALE1      0.055695  0.000000  0.000000        0.00000
SCALE2      0.000000  0.075347  0.000000        0.00000
SCALE3      0.000000  0.000000  0.076365        0.00000
ATOM      1  N   TYR A 139      10.241   7.920   5.000  1.00 10.00           N
ATOM      2  CA  TYR A 139      10.853   7.555   6.271  1.00 10.00           C
ATOM      3  C   TYR A 139      12.362   7.771   6.227  1.00 10.00           C
ATOM      4  O   TYR A 139      12.955   8.272   7.181  1.00 10.00           O
ATOM      5  CB  TYR A 139      10.540   6.098   6.617  1.00 10.00           C
ATOM      6  CG  TYR A 139       9.063   5.805   6.749  1.00 10.00           C
ATOM      7  CD1 TYR A 139       8.316   5.391   5.654  1.00 10.00           C
ATOM      8  CD2 TYR A 139       8.414   5.943   7.969  1.00 10.00           C
ATOM      9  CE1 TYR A 139       6.966   5.122   5.770  1.00 10.00           C
ATOM     10  CE2 TYR A 139       7.064   5.676   8.095  1.00 10.00           C
ATOM     11  CZ  TYR A 139       6.345   5.266   6.993  1.00 10.00           C
ATOM     12  OH  TYR A 139       5.000   5.000   7.113  1.00 10.00           O
ATOM     13  HA ATYR A 139      10.583   7.992   7.177  0.50 10.00           H
ATOM     14  HB2ATYR A 139      10.938   5.457   5.830  0.50 10.00           H
ATOM     15  HB3ATYR A 139      11.014   5.853   7.567  0.50 10.00           H
ATOM     16  HD1ATYR A 139       8.799   5.277   4.695  0.50 10.00           H
ATOM     17  HD2ATYR A 139       8.974   6.264   8.835  0.50 10.00           H
ATOM     18  HE1ATYR A 139       6.400   4.801   4.908  0.50 10.00           H
ATOM     19  HE2ATYR A 139       6.575   5.788   9.051  0.50 10.00           H
ATOM     20  HH ATYR A 139       4.710   5.148   8.037  0.50 10.00           H
ATOM     21  DA BTYR A 139      10.557   8.334   6.899  0.50 10.00           D
ATOM     22  DB2BTYR A 139      10.938   5.457   5.830  0.50 10.00           D
ATOM     23  DB3BTYR A 139      11.014   5.853   7.567  0.50 10.00           D
ATOM     24  DD1BTYR A 139       8.799   5.277   4.695  0.50 10.00           D
ATOM     25  DD2BTYR A 139       8.974   6.264   8.835  0.50 10.00           D
ATOM     26  DE1BTYR A 139       6.400   4.801   4.908  0.50 10.00           D
ATOM     27  DE2BTYR A 139       6.575   5.788   9.051  0.50 10.00           D
ATOM     28  DH BTYR A 139       4.710   5.148   8.037  0.50 10.00           D
"""

def get_results_from_validate_H(neutron_distances, pdb_str):
  pdb_interpretation_phil = iotbx.phil.parse(
    input_string = grand_master_phil_str, process_includes = True)
  pi_params = pdb_interpretation_phil.extract()
  pi_params.pdb_interpretation.use_neutron_distances = neutron_distances

  pdb_inp = iotbx.pdb.input(lines=pdb_str.split("\n"), source_info=None)
  model = mmtbx.model.manager(
      model_input = pdb_inp,
      build_grm   = True,
      pdb_interpretation_params = pi_params)

  c = validate_H(model)
  r = c.validate_inputs()
  c.run()
  results = c.get_results()
  return results

def exercise():
  results = get_results_from_validate_H(
    neutron_distances = True,
    pdb_str = pdb_str)

  oc = results.overall_counts_hd
  hd_atoms_with_occ_0 = oc.hd_atoms_with_occ_0
  assert (oc.count_h == 30)
  assert (oc.count_d == 36)
  assert (oc.count_h_protein == 30)
  assert (oc.count_d_protein == 29)
  assert (oc.count_h_water == 0)
  assert (oc.count_d_water == 7)
  assert (oc.count_water == 5)
  assert (oc.count_water_0h == 1)
  assert (oc.count_water_1h == 1)
  assert (oc.count_water_2h == 1)
  assert (oc.count_water_altconf == 1)
  assert (oc.count_water_no_oxygen == 1)

  answer = ['DD22ALEU A   3 ', ' HB2ASER A   5 ']
  for item, answer in zip(hd_atoms_with_occ_0, answer):
    assert(item[0][5:-1] == answer)

  renamed_answer = [('DB2', 'DB3'), ('DB3', 'DB2'),('DB2', 'DB3'),
    ('DB3', 'DB2'),('DB2', 'DB3'), ('DB3', 'DB2')]
  renamed = results.renamed
  for entry, answer in zip(renamed, renamed_answer):
    oldname = entry[2].strip()
    newname = entry[1].strip()
    assert(oldname == answer[0])
    assert(newname == answer[1])

  hd_exchanged_sites = results.hd_exchanged_sites
  assert (len(results.hd_exchanged_sites.keys()) == 22)

  hd_sites_analysis  = results.hd_sites_analysis
  sites_different_xyz = hd_sites_analysis.sites_different_xyz
  xyz_answer = [0.0712]
  for item, answer in zip(sites_different_xyz, xyz_answer):
    assert approx_equal(item[2],answer, 1.e-2)

  sites_different_b   = hd_sites_analysis.sites_different_b
  b_answer = [-2]
  for item, answer in zip(sites_different_b, b_answer):
    assert approx_equal(item[2],answer, 1.e-1)

  sites_sum_occ_not_1 = hd_sites_analysis.sites_sum_occ_not_1
  sum_occ_answer=[0.58, 0.9]
  for item, answer in zip(sites_sum_occ_not_1, sum_occ_answer):
    assert approx_equal(item[2], answer, 1.e-2)

  sites_occ_sum_no_scattering = hd_sites_analysis.sites_occ_sum_no_scattering
  sum_scatt_answer=[0.4, 0.36]
  for item, answer in zip(sites_occ_sum_no_scattering, sum_scatt_answer):
    assert approx_equal(item[3], answer, 1.e-2)

  missing_HD_atoms   = results.missing_HD_atoms
  # XXX TODO

# ------------------------------------------------------------------------------
# Input has H and D everywhere (all exchanged)
# a) The C beta DB2 and DB3 atoms are swapped
# b) The C beta HB2 and HB3 atoms are swapped
# ------------------------------------------------------------------------------
def exercise1():
  renamed_answer = [('DB2', 'DB3')]

  # a) DB2 and DB3 swapped
  results1 = get_results_from_validate_H(
    neutron_distances = True,
    pdb_str = pdb_str1a)

  for entry, answer in zip(results1.renamed, renamed_answer):
    oldname = entry[2].strip()
    newname = entry[1].strip()
    assert(oldname == answer[0])
    assert(newname == answer[1])

  # HB2 and HB3 swapped --> D atoms are renamed
  results2 = get_results_from_validate_H(
    neutron_distances = True,
    pdb_str = pdb_str1b)

  for entry, answer in zip(results1.renamed, renamed_answer):
    oldname = entry[2].strip()
    newname = entry[1].strip()
    assert(oldname == answer[0])
    assert(newname == answer[1])

# ------------------------------------------------------------------------------
# PROPERTIES H/D SITES
# a) HA and DA have different coordinates
# b) HD1 and DD1 have different B factors
# c) HH and DH have different coordinates and are within cutoff distance to
#    create a warning for zero scattering sum (Note that HH and DH may be at
#    different positions)
# ------------------------------------------------------------------------------
def exercise2():
  results = get_results_from_validate_H(
    neutron_distances = True,
    pdb_str = pdb_str2)
  hd_sites_analysis  = results.hd_sites_analysis

  assert (len(results.hd_exchanged_sites.keys()) == 8)

  sites_different_xyz = hd_sites_analysis.sites_different_xyz
  xyz_answer = [
    ('pdb=" HA ATYR A 139 "', 'pdb=" DA BTYR A 139 "', 0.141),
    ('pdb=" HH ATYR A 139 "', 'pdb=" DH BTYR A 139 "', 0.704)]
  for item, answer in zip(sites_different_xyz, xyz_answer):
    assert approx_equal(item[2],answer[2], 1.e-2)
    assert (item[0].strip() == answer[0].strip())
    assert (item[1].strip() == answer[1].strip())

  sites_different_b   = hd_sites_analysis.sites_different_b
  b_answer = [('pdb=" HD1ATYR A 139 "', 'pdb=" DD1BTYR A 139 "', -2)]
  for item, answer in zip(sites_different_b, b_answer):
    assert approx_equal(item[2],answer[2], 1.e-1)
    assert (item[0].strip() == answer[0].strip())
    assert (item[1].strip() == answer[1].strip())

  sites_occ_sum_no_scattering = hd_sites_analysis.sites_occ_sum_no_scattering
  sum_scatt_answer=[('pdb=" HH ATYR A 139 "', 'pdb=" DH BTYR A 139 "', 0.6, 0.4)]
  for item, answer in zip(sites_occ_sum_no_scattering, sum_scatt_answer):
    assert approx_equal(item[3], answer[3], 1.e-2)
    assert (item[0].strip() == answer[0].strip())
    assert (item[1].strip() == answer[1].strip())

# ------------------------------------------------------------------------------
# OCCUPANCIES
# a) HD2 and DD2 have sum occupancy < 1
# b) HE2 and DD2 have sum occupancy > 1
# c) HB2 has 0 occupancy (while having exchanged partner DB2)
# d) HD1 has occupancy < 1 (no exchanged partner)
# ------------------------------------------------------------------------------
def exercise3():
  results = get_results_from_validate_H(
    neutron_distances = True,
    pdb_str = pdb_str3)
  hd_sites_analysis  = results.hd_sites_analysis

  sites_sum_occ_not_1 = hd_sites_analysis.sites_sum_occ_not_1

  sum_occ_answer=[
    ('pdb=" HD2ATYR A 139 "', 'pdb=" DD2BTYR A 139 "', 0.9),
    ('pdb=" HE2ATYR A 139 "', 'pdb=" DE2BTYR A 139 "', 1.1)]
  for item, answer in zip(sites_sum_occ_not_1, sum_occ_answer):
    assert approx_equal(item[2], answer[2], 1.e-2)
    assert (item[3] is not None and item[4] is not None) # make sure xyz exist
    assert (item[0].strip() == answer[0].strip())
    assert (item[1].strip() == answer[1].strip())

  oc = results.overall_counts_hd
  hd_atoms_with_occ_0 = oc.hd_atoms_with_occ_0
  single_hd_atoms_occ_lt_1 = oc.single_hd_atoms_occ_lt_1

  occ_0_answer = ['pdb=" HB2ATYR A 139 "']
  for item, answer in zip(hd_atoms_with_occ_0, occ_0_answer):
    assert (item[0].strip() == answer.strip())
    assert (item[1] is not None) # make sure xyz exist

  occ_lt_1_answer = [('pdb=" HD1 TYR A 139 "', 0.5)]
  for item, answer in zip(single_hd_atoms_occ_lt_1, occ_lt_1_answer):
    assert (item[0].strip() == answer[0].strip())
    assert (item[1] == answer[1])
    assert (item[2] is not None) # make sure xyz exist

# ------------------------------------------------------------------------------
# MISSING ATOMS
# Model has only H atoms
# H, HE1 and HB2 are missing
# (takes into account naming ambiguity HB1+HB2 and HB2+HB3)
# ------------------------------------------------------------------------------
def exercise4():
  results = get_results_from_validate_H(
    neutron_distances = True,
    pdb_str = pdb_str4)
  missing = results.missing_HD_atoms

  missing_answer = [('pdbres="TYR A 139 "', ['HE1', 'H', 'HB2'])]
  for item, answer in zip(missing, missing_answer):
    assert (item[0].strip() == answer[0].strip())
    assert (item[2] is not None) # make sure xyz exist
    for atom, aatom in zip(item[1], answer[1]):
      assert (atom.strip() == aatom.strip())

# ------------------------------------------------------------------------------
# MISSING ATOMS
# Model has only D atoms
# H, HE1 and HB2 are missing --> result uses H naming convention!
# (takes into account naming ambiguity HB1+HB2 and HB2+HB3)
# ------------------------------------------------------------------------------
def exercise5():
  results = get_results_from_validate_H(
    neutron_distances = True,
    pdb_str = pdb_str5)
  missing = results.missing_HD_atoms

  missing_answer = [('pdbres="TYR A 139 "', ['HE1', 'H', 'HB2'])]
  for item, answer in zip(missing, missing_answer):
    assert (item[0].strip() == answer[0].strip())
    assert (item[2] is not None) # make sure xyz exist
    for atom, aatom in zip(item[1], answer[1]):
      assert (atom.strip() == aatom.strip())

# ------------------------------------------------------------------------------
# MISSING ATOMS
# Model has exchanged sites
# H --> missing
# HD2 --> missing
# CG --> missing, should not be in results because it is non-H atom
# HE1 --> is present as DE1 in conf B but missing HE1 in conf A
# HB3 --> is present as HB3 in conf A but missing DB3 in conf B
# ------------------------------------------------------------------------------
def exercise6():
  results = get_results_from_validate_H(
    neutron_distances = True,
    pdb_str = pdb_str6)
  missing = results.missing_HD_atoms

  missing_answer = [('pdbres="TYR A 139 "', ['HE1', 'H', 'HD2', 'HB3'])]
  for item, answer in zip(missing, missing_answer):
    assert (item[0].strip() == answer[0].strip())
    assert (item[2] is not None) # make sure xyz exist
    for atom, aatom in zip(item[1], answer[1]):
      assert (atom.strip() == aatom.strip())
      assert (atom.strip() != 'CG')

# ------------------------------------------------------------------------------
# BOND OUTLIERS
# Model has only H atoms and only following outliers
# Bond OH--HH,   observed: 0.769, delta from target:  0.210
# Bond CB--HB3,  observed: 0.930, delta from target:  0.159
# Bond CB--HB2,  observed: 0.936, delta from target:  0.153
# Bond CD2--HD2, observed: 1.209, delta from target: -0.129
# ------------------------------------------------------------------------------
def exercise7():
  results = get_results_from_validate_H(
    neutron_distances = True,
    pdb_str = pdb_str7)
  outliers_bonds = results.outliers_bonds

  outliers_bond_answer = [
    [' A 139 ATYR  HH ', 0.769, 0.98 ],
    [' A 139 ATYR  HB3', 0.930, 1.09 ],
    [' A 139 ATYR  HB2', 0.936, 1.09 ],
    [' A 139 ATYR  HD2', 1.209, 1.08 ] ]

  for item, answer in zip(outliers_bonds, outliers_bond_answer):
    assert (item[0].strip() == answer[0].strip()) # pdb_str
    assert (item[5] is not None)                  # make sure xyz exist
    assert approx_equal(item[2],answer[1], 1.e-2) # bond length model
    assert approx_equal(item[4],answer[2], 1.e-1) # target

# ------------------------------------------------------------------------------
# BOND OUTLIERS
# Model has only D atoms and only following outliers
# Bond CE2--DE2, observed: 0.876, delta from target:  0.203
# Bond CB--DB3,  observed: 1.264, delta from target: -0.174
# Bond CD1--DD1, observed: 1.236, delta from target: -0.156
# Bond CB--DB2,  observed: 1.002, delta from target:  0.087
# ------------------------------------------------------------------------------
def exercise8():
  results = get_results_from_validate_H(
    neutron_distances = True,
    pdb_str = pdb_str8)
  outliers_bonds = results.outliers_bonds

  outliers_bond_answer = [
    [' A 139  TYR  DE2', 0.876, 1.08],
    [' A 139  TYR  DB3', 1.264, 1.09],
    [' A 139  TYR  DD1', 1.236, 1.08],
    [' A 139  TYR  DB2', 1.002, 1.09] ]

  for item, answer in zip(outliers_bonds, outliers_bond_answer):
    assert (item[0].strip() == answer[0].strip()) # pdb_str
    assert (item[5] is not None)                  # make sure xyz exist
    assert approx_equal(item[2],answer[1], 1.e-2) # bond length model
    assert approx_equal(item[4],answer[2], 1.e-1) # target

# ------------------------------------------------------------------------------
# BOND OUTLIERS
# Model has H and D atoms, and only the following outliers
# Bond CE2--DE2, observed: 0.876, delta from target:  0.203
# Bond CB--DB3,  observed: 1.264, delta from target: -0.174
# Bond CD1--DD1, observed: 1.236, delta from target: -0.156
# Bond CB--DB2,  observed: 1.002, delta from target:  0.087
# ------------------------------------------------------------------------------
def exercise9():
  results = get_results_from_validate_H(
    neutron_distances = True,
    pdb_str = pdb_str9)
  outliers_bonds = results.outliers_bonds

  outliers_bond_answer = [
    [' A 139 ATYR  HB2',  0.893, 1.09],
    [' A 139 BTYR  DD1',  1.243, 1.08],
    [' A 139 BTYR  DH ',  1.123, 0.98],
    [' A 139 ATYR  HE2',  0.986, 1.08] ]

  for item, answer in zip(outliers_bonds, outliers_bond_answer):
    assert (item[0].strip() == answer[0].strip()) # pdb_str
    assert (item[5] is not None)                  # make sure xyz exist
    assert approx_equal(item[2],answer[1], 1.e-2) # bond length model
    assert approx_equal(item[4],answer[2], 1.e-1) # target

def exercise10():
  results = get_results_from_validate_H(
    neutron_distances = True,
    pdb_str = pdb_str10)
  outliers_angles = results.outliers_angles

  outliers_angles_answer = [
    [' A 139 ATYR  HA ',  123.01, 110.0, (10.583, 7.992, 7.177)],
    [' A 139 BTYR  DA ',  121.11, 109.0, (10.557, 8.334, 6.899)]  ]

  for item, answer in zip(outliers_angles, outliers_angles_answer):
    assert (item[0].strip() == answer[0].strip()) # pdb_str
    assert (item[5] is not None)                  # make sure xyz exist
    assert approx_equal(item[2],answer[1], 1.e-2) # angle in model
    assert approx_equal(item[4],answer[2], 1.e-1) # target

# ------------------------------------------------------------------------------
# CHECK HD STATE (hd_state)
# This is not a result but used internally to decide if H/D site analysis is
# necessary or not
# ------------------------------------------------------------------------------
def exercise_hd_state():
  pdb_interpretation_phil = iotbx.phil.parse(
    input_string = grand_master_phil_str, process_includes = True)

  pdb_inp = iotbx.pdb.input(lines=pdb_str4.split("\n"), source_info=None)
  model = mmtbx.model.manager(
      model_input = pdb_inp,
#      build_grm   = True, # to speed up test
      pdb_interpretation_params = pdb_interpretation_phil.extract())
  c = validate_H(model)
  assert (c.get_hd_state() == 'all_h')

  pdb_inp = iotbx.pdb.input(lines=pdb_str5.split("\n"), source_info=None)
  model = mmtbx.model.manager(
      model_input = pdb_inp,
#      build_grm   = True, # to speed up test
      pdb_interpretation_params = pdb_interpretation_phil.extract())
  c = validate_H(model)
  assert (c.get_hd_state() == 'all_d')

  pdb_inp = iotbx.pdb.input(lines=pdb_str3.split("\n"), source_info=None)
  model = mmtbx.model.manager(
      model_input = pdb_inp,
#      build_grm   = True, # to speed up test
      pdb_interpretation_params = pdb_interpretation_phil.extract())
  c = validate_H(model)
  assert (c.get_hd_state() == 'h_and_d')

def run():
  exercise()
  exercise1()
  exercise2()
  exercise3()
  exercise4()
  exercise5()
  exercise6()
  exercise7()
  exercise8()
  exercise9()
  exercise10()
  exercise_hd_state()

if (__name__ == "__main__"):
  t0 = time.time()
  run()
  print "OK. Time: %8.3f"%(time.time()-t0)

