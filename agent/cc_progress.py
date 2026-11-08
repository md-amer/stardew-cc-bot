"""Community Center progress: bundles complete and ingredient slots filled (30 bundles, The Missing Bundle excluded)."""
import sv
def progress():
    c = sv.call("cc")
    bs = [b for b in c["bundles"] if b["room"] != "Abandoned Joja Mart"]
    for b in bs:   # money bundles: the purchase sets only flag [0] (decompiled JunimoNoteMenu), so isBundleComplete stays false
        if b["room"] == "Vault" and b["ingredients"] and b["ingredients"][0]["done"]: b["complete"] = True
    done_b = sum(b["complete"] for b in bs)
    slots = sum(b["slots"] for b in bs)
    filled = sum(b["slots"] if b["complete"] else min(b["slots"], sum(g["done"] for g in b["ingredients"])) for b in bs)
    return done_b, len(bs), filled, slots
if __name__ == "__main__":
    d, n, f, s = progress()
    print(f"bundles {d}/{n} = {100*d/n:.1f}%   ingredient slots {f}/{s} = {100*f/s:.1f}%")
