"""Read-only, nonblocking backup-ignore advice for trusted, stable local projects.

Inspects index metadata and project-local ignore rules, never backup contents.
The caller must trust the installed Git selected from PATH. This is not a sandbox
for hostile repositories or a guarantee against concurrent filesystem changes.
"""
import os
from pathlib import Path
import stat
import time

from ci_evidence import bounded_run
from integrity import safe_path

BACKUP_NAMES = frozenset(('.factory-update-backups', '.factory-recovery-backups'))
OUTPUT_LIMIT = 16 * 1024
TIME_LIMIT = 5
METADATA_LIMIT = 32 * 1024 * 1024


def git_environment():
    """Retain process-launch necessities, not injected Git options or credentials."""
    allowed = {'PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'TEMP', 'TMP', 'LANG', 'LC_ALL'}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_GLOBAL=os.devnull,
               GIT_ALLOW_PROTOCOL='', GIT_PROTOCOL_FROM_USER='0', GIT_TERMINAL_PROMPT='0',
               GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0')
    return env


def result(status):
    messages = {
        'ignored': 'Backup directory is ignored by project-local rules; no tracked backup paths were found.',
        'unignored': 'Backup directory is not ignored by project-local rules. Review scoped ignore entries manually.',
        'tracked': 'Backup paths are already tracked in the index. Ignore rules cannot protect those tracked paths; review them manually.',
        'unknown': 'Backup ignore status is unknown; the project-local check was unavailable, unsupported or unsafe. Review the backup location manually.',
    }
    return {'status': status, 'scope': 'project-local rules only',
            'message': 'ADVISORY: '+messages[status]+' This advisory does not change or determine the backup/write outcome.'}


def inspect_backup_directory(project_root, backup_directory):
    """Return ignored/unignored/tracked/unknown without changing files or raising.

Only the two known backup containers immediately below an explicit project root
with a normal .git directory are supported. Linked worktrees and nested/discovered
repositories return unknown. Global/system excludes are deliberately not used.
Call after separately reporting the successful write; never treat this as a gate.
"""
    try:
        project, backup = Path(project_root).absolute(), Path(backup_directory).absolute()
        if str(project).startswith(('\\\\', '//')) or '..' in project.parts or backup.parent != project or backup.name not in BACKUP_NAMES:
            return result('unknown')
        project, backup = safe_path(project), safe_path(backup)
        if not project.is_dir() or not backup.is_dir():
            return result('unknown')
        git_dir = safe_path(project/'.git')
        if not git_dir.is_dir() or (git_dir/'commondir').exists():
            return result('unknown')
        # No descendant of the backup container is opened, scanned or supplied
        # to check-ignore. Root-local rules suffice to exclude the entire folder.
        for path in (project/'.gitignore', git_dir/'config', git_dir/'config.worktree',
                     git_dir/'index', git_dir/'info/exclude'):
            path = safe_path(path)
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_size > METADATA_LIMIT:
                return result('unknown')
        env = git_environment()
        argv = ['git', '--no-pager', '--no-optional-locks',
                '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath='+os.devnull,
                '-c', 'core.excludesFile='+os.devnull, '-C', str(project),
                '--git-dir='+str(git_dir), '--work-tree='+str(project)]
        deadline = time.monotonic()+TIME_LIMIT

        def run(args):
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise ValueError('Advisory deadline exceeded')
            return bounded_run(argv+args, env, OUTPUT_LIMIT, timeout=remaining)

        status, tracked = run(['--literal-pathspecs', 'ls-files', '--cached', '-z', '--', backup.name])
        if status:
            return result('unknown')
        if tracked:
            prefix = backup.name.encode('ascii')
            if not tracked.endswith(b'\0') or any(name != prefix and not name.startswith(prefix+b'/')
                                                   for name in tracked[:-1].split(b'\0')):
                return result('unknown')
            return result('tracked')
        # check-ignore accepts pathnames, not pathspec magic. Both allowed names
        # are fixed literal basenames, and no descendant path is supplied.
        status, output = run(['check-ignore', '--quiet', '--no-index', '--', backup.name])
        if output or status not in (0, 1):
            return result('unknown')
        return result('ignored' if status == 0 else 'unignored')
    except Exception:
        # An optional advisory must never turn a completed backup into a reported
        # write failure or expose Git stderr, configuration or arbitrary filenames.
        return result('unknown')
