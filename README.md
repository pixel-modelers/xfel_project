Get only the xfel module

```
mamba create -n xfel -c conda-forge cctbx-base dials dxtbx libboost-devel libboost-python-devel python=3.9 -y
conda activate xfel
git clone https://github.com/pixel-modelers/xfel_project.git
cd xfel_project
cmake -B build .
make -C build -j4 install
pip install -e
xfel-merge -c -e10 -a2 > xfel_merge_documentation.txt
```

