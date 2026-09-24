"""Wake Phrase Lab command line (Step 1: fetch, build, sources, inspect).

  python -m wakelab fetch [--optional] [--only ID ...]   download + record provenance
  python -m wakelab build                                 build the phonetic corpus cache
  python -m wakelab sources                               licenses / provenance summary
  python -m wakelab inspect TEXT [TEXT ...] [--phonemes "EH1 R IY0 AH0"] [--json] [--no-save]
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
    return 0
