"""Validate proposed operational metadata; never probe or enable a provider."""
import copy

def operations(config):
    defaults = {
        'identities': [], 'tool_recipes': [],
        'autonomy': {'mode':'manual','kill_switch':'Human stop request; stop scheduling and cancel pending work safely',
                     'max_items_per_hour':0,'allowed_submitters':[],'rejected_items':'Record reason and stop; do not retry without a new authorized decision'},
        'review': {'required_approvals':0,'independent':False,'distinct_providers':False},
        'visual_checks': {'required':False,'reference':'Unconfirmed or not applicable','method':'Rendered comparison and human review when relevant'}
    }
    supplied = config.get('operations',{})
    if not isinstance(supplied,dict) or not set(supplied) <= set(defaults):
        raise ValueError('Unknown operations field')
    result = copy.deepcopy(defaults)
    for key,value in supplied.items():
        if isinstance(defaults[key],dict):
            if not isinstance(value,dict) or not set(value) <= set(defaults[key]):
                raise ValueError('Invalid operations section: ' + key)
            result[key].update(value)
        else:
            result[key] = value
    for key,fields in (
        ('identities', {'provider','account','scope','git_author','status','evidence'}),
        ('tool_recipes', {'provider','headless_command','structured_output','tool_restrictions','auth_probe','auth_status','auth_evidence'})
    ):
        if not isinstance(result[key],list):
            raise ValueError(key + ' must be a list')
        for item in result[key]:
            if not isinstance(item,dict) or set(item) != fields or any(not isinstance(v,str) or not v.strip() for v in item.values()):
                raise ValueError('Invalid ' + key + ' record; see intake reference')
    a = result['autonomy']
    if a['mode'] not in ('manual','bounded') or type(a['max_items_per_hour']) is not int or a['max_items_per_hour'] < 0:
        raise ValueError('Invalid autonomy mode or rate limit')
    if not isinstance(a['allowed_submitters'],list) or any(not isinstance(v,str) or not v.strip() for v in a['allowed_submitters']):
        raise ValueError('Autonomy allowed_submitters must be a string list')
    if any(not isinstance(a[k],str) or not a[k].strip() for k in ('kill_switch','rejected_items')):
        raise ValueError('Autonomy stopping and rejection behavior are required')
    if a['mode'] == 'bounded' and (not a['allowed_submitters'] or a['max_items_per_hour'] == 0):
        raise ValueError('Bounded autonomy requires named submitters and a positive rate limit')
    r = result['review']
    if type(r['required_approvals']) is not int or r['required_approvals'] < 0 or any(type(r[k]) is not bool for k in ('independent','distinct_providers')):
        raise ValueError('Invalid review policy')
    v = result['visual_checks']
    if type(v['required']) is not bool or any(not isinstance(v[k],str) or not v[k].strip() for k in ('reference','method')):
        raise ValueError('Invalid visual-check policy')
    return result
