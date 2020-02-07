import salt.utils.platform

__virtualname__ = 'get'


def __virtual__():
    proxytype = __pillar__.get('proxy', {}).get('proxytype')
    if salt.utils.platform.is_proxy() and proxytype == 'junos':
        return __virtualname__
    return False


def running_config():
    return __salt__['junos.rpc']('get-config')['rpc_reply']['configuration']
