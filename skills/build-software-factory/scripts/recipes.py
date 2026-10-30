"""Validate optional design metadata. Nothing here schedules, records or narrates."""
import json
INTAKE_FIELDS = frozenset(('coverage','mechanism','cadence','timezone','window','window_evidence'))
VIDEO_FIELDS = frozenset(('composition','voice_provider','delivery_channel','branding','duration_seconds','captions','media_format','triggers'))


def video_triggers(video):
    selected=video.get('triggers',['post_g3_release'])
    if not isinstance(selected,list) or any(not isinstance(v,str) or v not in ('pre_merge_preview','post_g3_release') for v in selected) or len(set(selected))!=len(selected) or (video['enabled'] and not selected):
        raise ValueError('Video triggers must be unique pre_merge_preview/post_g3_release values; enabled video needs a trigger')
    return selected if video['enabled'] else []


def text_fields(value, fields):
    if any(not isinstance(value[key], str) or not value[key].strip() or len(value[key])>2000 for key in fields):
        raise ValueError('Recipe text must be nonempty and at most 2000 characters')


def intake_design(intake):
    result = {'coverage':'around_the_clock', 'mechanism':'unconfirmed',
              'cadence':'unconfirmed; choose within provider limits and budget',
              'timezone':'unconfirmed', 'window':'none', 'window_evidence':'none',
              **{key:intake[key] for key in INTAKE_FIELDS if key in intake}}
    text_fields(result, INTAKE_FIELDS)
    if result['coverage'] not in ('around_the_clock','operator_window') or result['mechanism'] not in ('unconfirmed','polling','event_driven'):
        raise ValueError('Invalid continuous-intake coverage or mechanism')
    if result['coverage']=='around_the_clock' and result['window']!='none':
        raise ValueError('A restricted window requires explicit operator_window coverage')
    if result['coverage']=='operator_window':
        for key in ('timezone','window','window_evidence'):
            normalized=' '.join(result[key].casefold().split()).rstrip(' .:')
            if normalized in ('none','unconfirmed','unknown','tbd','n/a','not configured','pending') or normalized.startswith(('unconfirmed:','unknown:','tbd:')):
                raise ValueError('Operator window requires timezone, actual window and evidence of the operator choice')
    return result


def video_design(video):
    result = {'composition':'unconfirmed; choose an installed project-fitting editor/compositor; Remotion is optional',
              'voice_provider':'ElevenLabs preferred when chosen/available; narration approval unverified',
              'delivery_channel':'approved local artifact; sharing destination and authority unconfirmed',
              'branding':'project name, actual subject revision or PR, date; adapt to approved project branding',
              'duration_seconds':60, 'captions':True, 'media_format':'mp4',
              **{key:video[key] for key in VIDEO_FIELDS if key in video}}
    text_fields(result, VIDEO_FIELDS-{'duration_seconds','captions','triggers'})
    video_triggers(video)
    if type(result['duration_seconds']) is not int or not 1<=result['duration_seconds']<=600:
        raise ValueError('Video duration must be an integer 1..600 seconds; 30..90 is the normal single-change target')
    if type(result['captions']) is not bool or result['media_format'] not in ('mp4','webm'):
        raise ValueError('Invalid video captions flag or media format')
    return result


def proposal(kind, values):
    design = intake_design(values) if kind=='intake' else video_design(values)
    title = 'Intake coverage' if kind=='intake' else 'Done-video'
    note = 'Mode/status and live authority remain in policy controls; this is not a live schedule.' if kind=='intake' else 'Enabled preference: '+str(values['enabled']).lower()+'. Disabled requests no video. Read current config/policy and done-video-recipe.md when present (otherwise the installed builder recipe); resolve authority before capture/narration/delivery.'
    return '<!-- factory-'+kind+'-design:start -->\n## '+title+' design (proposal, not execution authority)\n```json\n'+json.dumps(design,indent=2,ensure_ascii=False)+'\n```\n\n'+note+'\n<!-- factory-'+kind+'-design:end -->'


def refresh_proposal(text, kind, before, after):
    text = text.replace('\r\n','\n')
    start, end = '<!-- factory-'+kind+'-design:start -->', '<!-- factory-'+kind+'-design:end -->'
    if text.count(start)!=text.count(end) or text.count(start)>1:
        raise ValueError('Ambiguous recipe design block; preserve and review manually')
    if start not in text:
        return text.rstrip()+'\n\n'+proposal(kind,after)+'\n'
    a, b = text.index(start), text.index(end)+len(end)
    if b<a or text[a:b]!=proposal(kind,before):
        raise ValueError('Customized recipe design block preserved; review a narrow manual migration')
    return text[:a]+proposal(kind,after)+text[b:]
