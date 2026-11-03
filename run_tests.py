"""Run the plugin's offline unittest suite from any working directory."""
import sys
import unittest
from pathlib import Path


def main():
    tests = Path(__file__).resolve().parent / 'skills' / 'build-software-factory' / 'scripts'
    try:
        suite = unittest.defaultTestLoader.discover(str(tests), pattern='test_*.py')
    except (ImportError, OSError) as exc:
        print('ERROR: could not discover plugin tests: ' + str(exc), file=sys.stderr)
        return 2
    if suite.countTestCases() == 0:
        print('ERROR: no plugin tests were discovered; no tests ran.', file=sys.stderr)
        return 2
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
