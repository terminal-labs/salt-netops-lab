import json
import os

def running_config_report(tgt='*', tgt_type='glob', save_as=''):
    minions_ret = __salt__['salt.execute'](tgt, 'get.running_config', tgt_type=tgt_type)

    report = "The following is the minion's running configuration: \n\n"
    for minion in minions_ret:
        report += "{0}: \n\n".format(minion)

        running_config = minions_ret[minion]
        if isinstance(running_config, dict):
            running_config = json.dumps(running_config, indent=2)
        report += running_config

        report += '\n\n'
    report += "End of report.\n"

    if save_as:
        path, filename = os.path.split(save_as)
        if not os.path.isdir(path):
            os.makedirs(path)
        with open(save_as, 'w') as file_:
            file_.write(report)
        return "Running config report saved to: {0}".format(save_as)

    return report
