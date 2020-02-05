import salt.utils.platform

__virtualname__ = 'config'


def __virtual__():
    proxytype = __pillar__.get('proxy', {}).get('proxytype')
    if salt.utils.platform.is_proxy() and proxytype == 'junos':
        return __virtualname__
    return False


def load(template, **kwargs):
    return __salt__['junos.load'](template, **kwargs)


def diff():
    diff_ret = __salt__['junos.diff']()
    if diff_ret['out']:
        return diff_ret['message']
    else:
        raise ValueError("diff failed: {0}".format(diff_ret))
    

def commit():
    return __salt__['junos.commit']()


def rollback():
    return __salt__['junos.rollback']()

