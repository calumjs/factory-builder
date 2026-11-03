"""Guidance assertions follow the generated entrypoint's actual local guide link."""
def phase_text(files,phase):
    skill=files[f'.claude/skills/factory-{phase}/SKILL.md']
    guide=f'phase-{phase}-guide.md'
    assert '../../../'+guide in skill, 'Phase entrypoint must route to its detailed guide'
    assert guide in files, 'Referenced phase guide must be generated'
    return skill+'\n'+files[guide]


def phase_text_at(root,phase):
    names=(f'.claude/skills/factory-{phase}/SKILL.md',f'phase-{phase}-guide.md')
    return phase_text({name:(root/name).read_text(encoding='utf-8') for name in names},phase)
