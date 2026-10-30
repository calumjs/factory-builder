# Scheduler design (inactive)

The factory has no installed scheduler or atomic cross-process admission. `run.py
schedule --kind cron|launchd|windows|github` prints a non-executable JSON proposal;
it does not create a runnable job. Do not copy a proposal or this example into an
active scheduler location. A scheduled pass needs separately authorized,
project-specific design and testing for exclusive admission, actual rate and budget
enforcement, stop handling, scoped identities, data and the platform command.

`factory-run.example.yml` is an inactive example outside `.github/workflows` and
is not a verified or authorized deployment. It must not be activated unchanged.
An issue snapshot is untrusted data and needs an explicit project repository/ready
and excluded-label policy; selection is advisory and never claims or edits issues.
