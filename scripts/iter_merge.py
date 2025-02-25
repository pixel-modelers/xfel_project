
def main():
    phil = """
input.parallel_file_load.method=uniform
#input.alist.file=allClust2_and_3.txt
#input.alist.type=tags
#input.alist.op=reject
filter.algorithm=unit_cell
filter.unit_cell.value.relative_length_tolerance=0.02
filter.outlier.min_corr=-1.0
filter.unit_cell.value.target_unit_cell={a},{b},{c},{al},{be},{ga}
filter.unit_cell.value.target_space_group=Auto
select.algorithm=significance_filter
select.significance_filter.sigma=0.05
merging.set_average_unit_cell=True
parallel.a2a=1
merging.error.model=ev11
statistics.n_bins=20
merging.d_min={d_min}
merging.merge_anomalous={merge_anom}
postrefinement.enable=False
postrefinement.algorithm=rs
scaling.model={model}
scaling.unit_cell={a},{b},{c},{al},{be},{ga}
scaling.space_group={symbol}
scaling.mtz.mtz_column_F="Iobs(+),SIGIobs(+),Iobs(-),SIGIobs(-)"
scaling.resolution_scalar=0.993420862158964
scaling.algorithm=mark{mark}
merging.set_average_unit_cell=True
statistics.report_ML=True
output.output_dir={outdir}
output.do_timing=True
output.log_level=1

#output.save_experiments_and_reflections=True
#output.expanded_bookkeeping=True
    """
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("dirnames", nargs="+", type=str)
    parser.add_argument("--tag", type=str, default="merge")
    parser.add_argument("--niter", default=3, type=int)
    parser.add_argument("--srun", type=str, default=None, help="mpi command prefix, e.g. `srun -c2` or `mpirun -n 10`")
    parser.add_argument("--dmin", default=2, type=float)
    parser.add_argument("--ucell", nargs=6, help="unit cell params a,b,c,alpha,beta,gamma in angstrom and degress", default=None, type=float)
    parser.add_argument("--symbol", type=str, help="space group lookup symbol e.g. P43212", default=None)
    parser.add_argument("--mergeAnom", action="store_true", help="combined +,- miller indices when merging")
    args = parser.parse_args()
    import os
    import sys
    import shutil
    import subprocess

    if args.ucell is None:
        raise TypeError("pass 6 items for the --ucell argument, e.g. --ucell 1 2 3 4 5 6")

    if args.symbol is None:
        raise TypeError("pass a space group symbol e.g. --symbol P4")

    for dirname in args.dirnames:
        if os.path.exists(dirname):
            phil = phil + f"\ninput.path={dirname}"
    outdir_prefix = args.tag
    mtz = None
    for i in range(args.niter):
        outdir = "%s.iter%d" % (outdir_prefix,i)

        if not os.path.exists(outdir):
            os.makedirs(outdir)
        mark = 1 if i==0 else 0
        model = "None" if i==0 else mtz
        #phil_arg = (model, mark, outdir)
        a,b,c,al,be,ga = args.ucell
        phil_str = phil.format(model=model,mark=mark,outdir=outdir, d_min=args.dmin,
            a=a,b=b,c=c,al=al,be=be,ga=ga, symbol=args.symbol, merge_anom=args.mergeAnom)
        phil_name = "_temp.phil"
        with open(phil_name, "w") as  o:
            o.write(phil_str)

        cmd = "cctbx.xfel.merge %s" %phil_name
        if args.srun is not None:
            cmd = f"{args.srun} {cmd}"
        shutil.copyfile(phil_name, os.path.join(outdir, phil_name))
        subprocess.call(cmd, shell=True)
        print("Done with merge ; iter %d / %d" % (i+1, args.niter))
        mtz = os.path.join(outdir, "iobs_all.mtz")
