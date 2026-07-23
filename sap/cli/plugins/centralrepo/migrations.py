import os
import sys
import yaml
from sap import get_logger
import sap.cli.core

from sap.cli.plugins.centralrepo.jenkinsfile import (
    parse_jenkinsfile_ci,
    evaulate_ddci_pipeline_config
)

from sap.cli.plugins.centralrepo.git import (
    GitCommand,
    get_local_repo_dirs
)


def mod_log():
    """ADT Module logger"""

    return get_logger()


class MigrationsGroup(sap.cli.core.CommandGroup):
    """Container for user commands."""

    def __init__(self):
        super().__init__('migration')


def _write_modified_jenkins_file(stream, all_tokens, first_token, last_token):
    idx = 0
    while idx < first_token:
        stream.write(all_tokens[idx].value)
        idx += 1

    idx = last_token + 1
    while idx < len(all_tokens) and all_tokens[idx].code == 'SP':
        idx += 1

    # states: none, call, open, params, none
    ddciPipelineAbapPackage = 'none'
    while idx < len(all_tokens):
        token = all_tokens[idx]

        if ddciPipelineAbapPackage == 'none' and token.code == 'WR' and token.value == 'ddciPipelineAbapPackage':
            ddciPipelineAbapPackage = 'call'
        elif ddciPipelineAbapPackage == 'call' and token.value == '(':
            ddciPipelineAbapPackage = 'open'
        elif ddciPipelineAbapPackage == 'open' and token.code == 'WR':
            ddciPipelineAbapPackage = 'params'
        elif ddciPipelineAbapPackage == 'params' and token.value == ')':
            ddciPipelineAbapPackage = 'none'

        if ddciPipelineAbapPackage != 'params':
            stream.write(all_tokens[idx].value)

        idx += 1


@MigrationsGroup.argument('-n', '--dryrun', action='store_true', default=False)
@MigrationsGroup.argument('basedir', default='/opt/ddci')
@MigrationsGroup.command()
def jenkinsfiletoproperties(connection, args):
    """Transform jenkins/Jenkinsfile_CI to .ddci/properties.yml"""

    console = sap.cli.core.get_console()

    mod_log().info('Changing to the local dir: %s', args.basedir)
    os.chdir(args.basedir)

    local_dirs = get_local_repo_dirs(args.basedir)

    git = GitCommand(console)

    ddci_jenkinsfile_path = os.path.join('jenkins', 'Jenkinsfile_CI')
    ddci_properties_path = os.path.join('.ddci', 'properties.yml')

    for repo in local_dirs:
        console.printout(f'* {repo}')

        jenkinsfile_ci = os.path.join(repo, ddci_jenkinsfile_path)
        console.printout(f' ? analyzing: {jenkinsfile_ci}')
        all_tokens = parse_jenkinsfile_ci(jenkinsfile_ci)
        console.printout(f' ? parsed: {jenkinsfile_ci}')
        jenkins_config, first_token, last_token = evaulate_ddci_pipeline_config(all_tokens)
        console.printout(f' ? evaluated: {jenkinsfile_ci}')
        if not jenkins_config:
            console.printout(f' ! skipped {jenkinsfile_ci}')
            continue

        general_config = jenkins_config.get('general', None)
        if general_config and 'abapGhRepo' in general_config:
            del general_config['abapGhRepo']

        dot_ddci = os.path.join(repo, '.ddci')
        try:
            os.makedirs(dot_ddci)
        except FileExistsError:
            pass

        ddci_properties = os.path.join(repo, ddci_properties_path)
        console.printout(f' ? writing: {ddci_properties}')
        if args.dryrun:
            sys.stdout.write(yaml.dump(jenkins_config, default_flow_style=False))
        else:
            try:
                with open(ddci_properties, 'w') as stream:
                    stream.write(yaml.dump(jenkins_config, default_flow_style=False))
            except OSError as ex_file:
                get_logger().info(str(ex_file))
                continue

        console.printout(f' ? writing: {jenkinsfile_ci}')
        if args.dryrun:
            _write_modified_jenkins_file(sys.stdout, all_tokens, first_token, last_token)
        else:
            with open(jenkinsfile_ci, 'w') as stream:
                _write_modified_jenkins_file(stream, all_tokens, first_token, last_token)

            git.add(ddci_jenkinsfile_path, repo)
            git.add(ddci_properties_path, repo)
            git.commit('ddci: move config from Jenkinsfile to properties.yml', repo,
                       message_body='''The configuration option abapGhRepo is no longer needed because
the pipeline ddciPipelineAbapPackage gets it from Jenkins scm and
the integration pipeline knows it from users who must pass it as a parameter.

Ref: https://github.wdf.sap.corp/factory/testing-jenkins-lib/commit/53d1e72465910ba5e4fd994a0ca97ec34b076f02

JIRA: SYSDEV-1035''')

    return 0
