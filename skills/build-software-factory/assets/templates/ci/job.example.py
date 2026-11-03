"""Inert portable CI step template. Adopt into trusted CI only after separate review.

Do not run a PR-supplied copy in a privileged job. The helper must be trusted/pinned
outside the change checkout; this file does not install it or configure a workflow.
"""
import json
import os
from pathlib import Path
import subprocess


def command(env):
    required=('FACTORY_PYTHON','FACTORY_TRUSTED_HELPER','FACTORY_REPO',
              'FACTORY_TESTED_SUBJECT_SHA','FACTORY_EVIDENCE_STORAGE_SHA')
    if any(not env.get(key) for key in required):raise ValueError('Missing explicit CI identity/path input')
    if not Path(env['FACTORY_PYTHON']).is_absolute() or not Path(env['FACTORY_TRUSTED_HELPER']).is_absolute():
        raise ValueError('Use approved absolute interpreter/helper paths')
    helper=Path(env['FACTORY_TRUSTED_HELPER']).resolve();checkout=Path(env['FACTORY_REPO']).resolve()
    if helper==checkout or checkout in helper.parents:
        raise ValueError('Trusted helper must be pinned outside the change checkout')
    argv=[env['FACTORY_PYTHON'],'-B',env['FACTORY_TRUSTED_HELPER'],
          '--repo',env['FACTORY_REPO'],'--factory',env.get('FACTORY_DIRECTORY','.software-factory'),
          '--subject',env['FACTORY_TESTED_SUBJECT_SHA'],'--storage',env['FACTORY_EVIDENCE_STORAGE_SHA'],
          '--stage',env.get('FACTORY_STAGE','pre-merge'),
          '--evidence-dir',env.get('FACTORY_EVIDENCE_DIRECTORY','docs/factory-evidence')]
    if env.get('FACTORY_ACTUAL_TARGET'):argv+=['--target',env['FACTORY_ACTUAL_TARGET']]
    tasks=json.loads(env.get('FACTORY_REQUIRED_TASKS','[]'))
    if not isinstance(tasks,list) or any(not isinstance(v,str) or not v.strip() for v in tasks):raise ValueError('CI-required task IDs must be an explicit JSON string array')
    for task in tasks:argv+=['--require-task',task]
    feature=(('FACTORY_FEATURE_POLICY','--feature-policy'),
             ('FACTORY_FEATURE_POLICY_SHA256','--feature-policy-sha256'),
             ('FACTORY_FEATURE_REQUEST','--feature-request'),
             ('FACTORY_FEATURE_BASE_SHA','--feature-base'))
    if any(key in env for key,_ in feature):
        if any(not env.get(key) for key,_ in feature) or env.get('FACTORY_STAGE','pre-merge')!='pre-merge':
            raise ValueError('Feature policy needs all four explicit inputs and pre-merge stage')
        for key,flag in feature:argv+=[flag,env[key]]
    return argv


if __name__=='__main__':
    try:raise SystemExit(subprocess.run(command(os.environ),shell=False).returncode)
    except (ValueError,OSError) as exc:raise SystemExit('CI template not configured: '+str(exc))
