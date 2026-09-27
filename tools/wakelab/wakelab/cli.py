"""Wake Phrase Lab command line (Step 1: fetch, build, sources, inspect).

  python -m wakelab fetch [--optional] [--only ID ...]   download + record provenance
  python -m wakelab build                                 build the phonetic corpus cache
  python -m wakelab sources                               licenses / provenance summary
  python -m wakelab inspect TEXT [TEXT ...] [--phonemes "EH1 R IY0 AH0"] [--json] [--no-save]
  python -m wakelab acoustic TEXT --phonemes ... --say "Hey Aria." [--say ...] [--pronounce "..."]
         [--thresholds 0.15 0.25 0.35] [--baseline aria:0.15] [--soak-hours H]   (SYNTHETIC)
  python -m wakelab rank [--extra TEXT ...] [--names-max-rank 1500]   Step 2: Pareto finalists
"""
import argparse
import json
import sys

from .config import settings, sources


def main(argv=None):
    ap = argparse.ArgumentParser(prog="wakelab", description="CAOSCare Wake Phrase Lab (Step 1)")
    ap.add_argument("--config", help="alternate settings YAML (default config/default.yaml)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--optional", action="store_true", help="also fetch optional sources (FDA drugs)")
    f.add_argument("--only", nargs="*")
    f.add_argument("--force", action="store_true")
    sub.add_parser("build")
    sub.add_parser("sources")
    i = sub.add_parser("inspect")
    i.add_argument("text", nargs="+", help="candidate words/phrases (quote multi-word phrases)")
    i.add_argument("--phonemes", help="explicit ARPAbet pronunciation (single candidate only)")
    i.add_argument("--json", action="store_true", help="print JSON instead of the explanation")
    i.add_argument("--no-save", action="store_true", help="do not write runs/<stamp>/report.*")
    a = sub.add_parser("acoustic", help="SYNTHETIC acoustic + adversarial + soak screening")
    a.add_argument("text")
    a.add_argument("--phonemes", help="intended pronunciation (ARPAbet) used to find adversarial neighbours")
    a.add_argument("--say", action="append", required=True, help="spoken positive text (repeatable)")
    a.add_argument("--pronounce", default="", help="pronunciation instruction for the TTS voices")
    a.add_argument("--thresholds", nargs="+", type=float, default=[0.15, 0.25, 0.35])
    a.add_argument("--baseline", action="append", default=[], help="KEYWORD:THRESHOLD comparison detector")
    a.add_argument("--soak-hours", type=float, help="cap the LibriSpeech soak (default: all of test-clean)")
    r = sub.add_parser("rank", help="Step 2: candidate generation + Pareto finalists (text stage)")
    r.add_argument("--extra", nargs="*", default=[], help="additional candidate words/phrases")
    r.add_argument("--names-max-rank", type=int, default=1500)
    args = ap.parse_args(argv)
    cfg = settings(args.config)

    if args.cmd == "fetch":
        from .corpus.registry import fetch
        fetch(only=args.only, include_optional=args.optional, force=args.force)
    elif args.cmd == "build":
        from .corpus.build import build
        print(json.dumps(build(cfg), indent=2))
    elif args.cmd == "sources":
        for sid, spec in sources().items():
            print(f"{sid}: {spec['license']}\n    {spec.get('attribution', '')}\n    use: {spec['use']}")
    elif args.cmd == "inspect":
        from .inspect import Lab
        from .report import render, save
        if args.phonemes and len(args.text) > 1:
            ap.error("--phonemes applies to a single candidate")
        lab = Lab(cfg)
        for text in args.text:
            r = lab.inspect(text, args.phonemes)
            human = render(r)
            print(json.dumps(r, indent=2, default=str) if args.json else human)
            if not args.no_save:
                print(f"[saved {save(r, human)}]", file=sys.stderr)
            print()
    elif args.cmd == "acoustic":
        _acoustic(args, cfg)
    elif args.cmd == "rank":
        _rank(args, cfg)
    return 0


def _acoustic(args, cfg):
    import os
    import re
    from .audio import evaluate, summary
    from .config import RUNS_DIR
    from .inspect import Lab
    slug = re.sub(r"[^a-z0-9]+", "-", args.text.lower()).strip("-")
    report = Lab(cfg).inspect(args.text, args.phonemes)
    specs = [(f"{slug}@{t}", args.text, t) for t in args.thresholds]
    for b in args.baseline:
        kw, th = b.rsplit(":", 1)
        specs.append((f"{re.sub(r'[^a-z0-9]+', '-', kw.lower())}@{th}", kw, float(th)))
    res = evaluate.run(args.text, report, args.say, args.pronounce, specs, args.soak_hours)
    summ = summary.summarize(res)
    text = summary.render(res, summ)
    out = os.path.join(RUNS_DIR, f"{res['generated_at'][:19].replace(':', '').replace('-', '')}_acoustic_{slug}")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as fh:
        json.dump({"result": res, "summary": summ, "inspect_verdict": report["verdict"]}, fh, indent=1, default=str)
    with open(os.path.join(out, "report.md"), "w", encoding="utf-8") as fh:
        fh.write("```\n" + text + "\n```\n")
    print(text)
    print(f"[saved {out}]", file=sys.stderr)


def _rank(args, cfg):
    import datetime
    import os
    from . import rank_report
    from .config import RUNS_DIR
    from .inspect import Lab
    from .rank import run
    res = run(Lab(cfg), extra=args.extra, names_max_rank=args.names_max_rank)
    text = rank_report.render(res)
    out = os.path.join(RUNS_DIR, datetime.datetime.now().strftime("%Y%m%dT%H%M%S") + "_rank")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    with open(os.path.join(out, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(text)
    print(f"[saved {out}]", file=sys.stderr)
