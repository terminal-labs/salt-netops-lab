def configured(name):
    """
    Ensure the device is configured. Uses net_config execution module.
    """
    ret = {
        'name': name,
        'result': None,
        'changes': {},
        'comment': ''
    }
    load_ret = __salt__['net_config.load'](name)
    session_name = load_ret.get('session_name')
    if session_name:
        diff = __salt__['net_config.diff'](session_name)
    else:
        diff = __salt__['net_config.diff']()
    
    if not diff:
        ret['result'] = True
        ret['comment'] = "The device is already configured."

        # abort session
        abort_ret = __salt__['net_config.abort'](session_name) if \
            session_name else __salt__['net_config.abort']()

        return ret
    elif __opts__["test"]:
        # there is a diff, but test=True
        ret['result'] = None
        ret['changes'] = {'diff': diff}
        ret['comment'] = "Changes would be applied but we are in test mode."

        # abort session
        abort_ret = __salt__['net_config.abort'](session_name) if \
            session_name else __salt__['net_config.abort']()

        return ret
    else:
        # there is a diff and we are not in test mode
        if session_name:
            commit_ret = __salt__['net_config.commit'](session_name)
        else:
            commit_ret = __salt__['net_config.commit']()
        ret['result'] = True
        ret['changes'] = {'old': '', 'new': diff}
        ret['comment'] = "The device has been successfully configured."
        return ret

