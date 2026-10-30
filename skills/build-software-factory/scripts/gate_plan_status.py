"""Read-only comparison of configured delivery gates and living records."""
import argparse
import json
import sys
from gates import gate_rows, requirements
from scoped_assessment import load


def compare(factory):
    _,config,research,text,_=load(factory)
    expected=requirements(config,research);rows=gate_rows(text);output=[]
    for gate in sorted(set(expected)|set(rows)):
        planned=expected.get(gate);recorded=rows.get(gate);differences=[]
        if planned is None:differences.append('extra')
        elif recorded is None:differences.append('missing')
        else:
            if planned['stage']!=recorded['stage']:differences.append('stage differs')
            if planned['design']!=recorded['design']:differences.append('design differs; inspect actual observation')
        output.append({'gate':gate,'planned':planned,'recorded':recorded,'differences':differences})
    return {'gates':output,'notice':'Read-only comparison of supplied records; differences are not automatic failures and no application checks were run or attested.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--factory',required=True);args=parser.parse_args()
    print(json.dumps(compare(args.factory),ensure_ascii=True,indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as exc:print('ERROR: '+str(exc),file=sys.stderr);sys.exit(1)
