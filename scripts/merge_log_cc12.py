import sys
import os
from pylab import *

def parse_log(merge_log):
    cc_vals = []
    res_vals = []
    lines = open(merge_log, "r").readlines()
    for i,l in enumerate(lines):
        if l.startswith("Bin") and "int" in l:
            while 1:
                l = lines[i+1]
                if l.startswith("All"):
                    break
                i += 1
                if "%" in l:
                    cc_data = l.split("%")[0]
                    cc = cc_data.split()[-1]
                    res1 = cc_data.split()[1]
                    res2 = cc_data.split()[3]
                    print(res1, res2,cc)
                    cc_vals.append(float(cc))
                    res_vals.append( (float(res1), float(res2)))
            break
    return res_vals,cc_vals


def main():
    from argparse import ArgumentParser
    ap = ArgumentParser()
    ap.add_argument("logfiles", nargs="+", help="log files written by cctbx.xfel.merge, default name is `iobs_main.log`")
    args = ap.parse_args()

    #xkcd()
    figure()
    gcf().set_size_inches((4,3))
    from itertools import cycle

    colors = cycle(["C0", "tomato", "forestgreen", "Deeppink" ])
    #colors = cycle([(152/255., 223/255., 138/255.), "tomato"])
    markers = cycle(["o", "s", "<"])
    labels = args.logfiles
    for ii,name in enumerate(args.logfiles):
        res_vals, cc_vals = parse_log(name)
        #plot(cc_vals, marker=next(markers), color=next(colors), ms=4,mec='w', mew=0.5,label=name)
        res_vals = [r[1] for r in res_vals]
        #plot(res_vals[::-1], cc_vals[::-1], marker=next(markers),  label=labels[ii],color=next(colors), ms=6,mec='w', mew=0.5)
        #plot(res_vals, cc_vals, marker=next(markers), color=next(colors), ms=7,mec='w', mew=0.5,
        #    label=os.path.basename(os.path.dirname(name)), lw=1)
        plot(res_vals, cc_vals, marker=next(markers), color=next(colors), ms=7,mec='w', mew=0.5,
            label=name, lw=1)
    gca().grid(1, lw=0.5, ls='--')
    gca().set_yticks(list(range(0,101,10)))
    #xlab = ["%.2f-%.2f"%(r1,r2) for r1,r2 in res_vals]
    #xtick = list(range(len(res_vals)))
    #gca().set_xticks(xtick)
    #gca().set_xticklabels(xlab, rotation=270)
    gca().tick_params(labelsize=16, length=0)
    gca().set_xlabel("resolution ($\AA$)", fontsize=20)
    gca().set_ylabel("CC1/2 (percent)", fontsize=20)
    plt.gca().tick_params(labelsize=19)
    #subplots_adjust(bottom=0.33, top=.98, left=.16, right=.98)
    legend(prop={"size":9})
    plt.gca().invert_xaxis()
    savefig("compare_merges.png", dpi=350)
    show()
