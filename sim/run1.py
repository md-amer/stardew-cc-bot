import sys, statistics as st, collections
import world as W, world1 as W1
def date(t): return "not done" if t is None else f"Y{t//112+1} {W.SE[(t//28)%4]} {t%28+1}"
def evaluate(plan=None, speeds=W.BOT, seeds=range(20), cap=336, verbose=True):
    fins=[]; bd=collections.defaultdict(list); miss=collections.Counter(); ws=[]
    for s in seeds:
        w=W1.World1(plan or W.Plan(), speeds, seed=s); t=w.run(cap); fins.append(t); ws.append(w)
        for b,d in w.done.items(): bd[b].append(d)
        for b in w.slots:
            if b not in w.done: miss[b]+=1
    y1=sum(1 for f in fins if f is not None and f<112)/len(fins)
    ok=sorted(f for f in fins if f is not None)
    if verbose:
        print(f"P(Year 1) {y1:.0%}  finished by cap {len(ok)}/{len(fins)}  median {date(ok[len(ok)//2]) if ok else '-'}")
        for b,v in sorted(bd.items(), key=lambda x: st.median(x[1])): print(f"   {b:16} {date(int(st.median(v))):18} {len(v)}/{len(fins)}")
        print("missing:", dict(miss))
    return y1, fins, ws
if __name__=="__main__":
    sp = W.HUMAN if "human" in sys.argv else W.BOT
    n = int(sys.argv[1]) if len(sys.argv)>1 and sys.argv[1].isdigit() else 10
    y1, f, ws = evaluate(speeds=sp, seeds=range(n))
    w=ws[0]; print("seed0 earned Y-total", w.earned, "levels", {k:w.level(k) for k in w.xp}, "floor", w.floor, "prof", w.prof)
    print("seed0 sample agendas:", w.agenda_log[10], w.agenda_log[40], w.agenda_log[70])
