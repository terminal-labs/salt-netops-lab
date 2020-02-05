import json


def running_config_report(minions):
    report = "The minions running configuration is as follows:\n\n"
    for minion in minions:
        report += "{0}: \n\n".format(minion)
        running_config = __salt__['salt.execute'](minion, 'get.running_config')[minion]
        if isinstance(running_config, dict):
            running_config = json.dumps(running_config, indent=2)
        report += running_config
        report += '\n\n'
    report += "End of the report.\n"
    return report

