"""gCTS methods"""

import os
import sys
from io import StringIO
import shutil
import subprocess
import re
import yaml
import json

from sap import get_logger
import sap.cli.core
import sap.cli.helpers
import sap.rest.gcts.simple
from sap.rest.gcts.remote_repo import Repository

from sap.cli.plugins.centralrepo.jenkinsfile import  parse_jenkinsfile_ci


CS_COMPONENT_MAPPING = {
    'SAPFCORE' : 'SAPSCORE_B',
    'SAPPCORE_H' : 'SAPPCORE_H',
    'SAPSCORE' : 'SAPSCORE_B',
    'SAPSCORE_B' : 'SAPSCORE_B',
    'SCORE_HOME' : 'SAPPCORE_H',
    'SAP_BASIS': 'SAP_BASIS',
}

def mod_log():
    """ADT Module logger"""

    return get_logger()


class DdciRepoGroup(sap.cli.core.CommandGroup):
    """Container for user commands."""

    def __init__(self):
        super().__init__('ddci')


class DdciRepository:

    def __init__(self, repo):
        self._repo = repo
        self._repo.wipe_data()
        self._ddci_check_status = ""

    @property
    def ddci_check_status(self):
        return self._ddci_check_status

    @ddci_check_status.setter
    def ddci_check_status(self, value):
        self._ddci_check_status = value
        return self

    @property
    def rid(self):
        return self._repo.rid

    @property
    def component(self):
        return self._repo.configuration.get('VCS_SAP_DELIVERY_COMP', '')

    @property
    def release(self):
        return self._repo.configuration.get('VCS_SAP_DELIVERY_RELEASE', '')

    @property
    def name(self):
        return self._repo.name

    @property
    def role(self):
        return self._repo.role

    @property
    def branch(self):
        return self._repo.branch

    @property
    def vsid(self):
        return self._repo.vsid

    @property
    def status(self):
        return self._repo.status

    @property
    def url(self):
        return self._repo.url


def fetch_ddci_repos(connection):
    response = sap.rest.gcts.simple.fetch_repos(connection)
    return (DdciRepository(repo) for repo in response if any((f'/{org}/' in repo.url.lower() for org in ['s4core', 's4corehome', 'asabap'])))


def get_local_repo_dirs(basedir):
    return [entry.name for entry in os.scandir(basedir) if entry.is_dir(follow_symlinks=False)]


def print_ddci_repolist(repos, display_header=True, white_list_columns=None):
    console = sap.cli.core.get_console()

    columns = (
        sap.cli.helpers.TableWriter.Columns()
        ('rid', 'ID')
        ('role', 'Role', default='N/a')
        ('component', 'Component', default='N/a')
        ('release', 'Release', default='N/a')
        ('branch', 'Branch', default='')
        ('vsid', 'vSID', default='N/a')
        ('status', 'Status', default='N/a')
        ('url', 'URL', default='N/a')
        .done()
    )

    tw = sap.cli.helpers.TableWriter(repos, columns, display_header=display_header, visible_columns=white_list_columns)
    tw.printout(console)


@DdciRepoGroup.argument('-n', '--no-heading', default=False, action='store_true')
@DdciRepoGroup.argument('-c', '--column', nargs='?', action='append')
@DdciRepoGroup.command('list')
# pylint: disable=unused-argument
def repolist(connection, args):
    """ls"""

    print_ddci_repolist(fetch_ddci_repos(connection), display_header=not args.no_heading, white_list_columns=args.column)

    return 0


class GitCommand:

    def __init__(self, console):
        self._git_bin = shutil.which('git')
        self.proc = None
        self._console = console

    def run(self, *args, cwd=None, stdin=None):
        _args = [self._git_bin]
        _args.extend(args)
        mod_log().info('Executing: %s', str(_args))
        self.proc = subprocess.Popen(_args, cwd=cwd, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            outs, errs = self.proc.communicate(timeout=60)
        except TimeoutExpired:
            self.proc.kill()
            outs, errs =self.proc.communicate()

        if self.proc.returncode != 0:
            get_logger().info(errs.decode('utf-8'))

        return outs.decode('utf-8').strip()

    def remote_get_url_origin(self, repo_dir):
        url =  self.run('remote', 'get-url', 'origin', cwd=repo_dir)

        if url is not None:
            url = re.sub('https://.*github\.', 'https://github.', url)

        return url

    def clone(self, url, dirname):
        return self.run('clone', url, dirname)

    def checkout(self, branch, repo_dir):
        return self.run('checkout', branch, cwd=repo_dir)

    def checkout_new_local_branch(self, branch, repo_dir):
        return self.run('checkout', '-b', branch, cwd=repo_dir)

    def add(self, file_rel_path, repo_dir):
        return self.run('add', file_rel_path, cwd=repo_dir)

    def commit(self, message, repo_dir, message_body=None):
        stdin = None
        if message_body:
            stdin = StringIO(message_body)

        return self.run('commit', '-m', message, cwd=repo_dir, stdin=stdin)

    def current_branch_name(self, repo_dir):
        return self.run('branch', '--show-current', cwd=repo_dir)


def load_yaml_file(filepath, console):
    try:
        with open(filepath, 'r') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLERROR as ex_yaml:
                console.printerr(str(ex_yaml))
    except OSError as ex_file:
        get_logger().info(str(ex_file))

    return None


def get_local_repo_systemconfig(repo_dir, console):
    return load_yaml_file(os.path.join(repo_dir, 'systemconfig.yml'))

def get_ddci_properties(repo_dir, console):
    return load_yaml_file(os.path.join(repo_dir, '.ddci', 'properties.yml'))

def write_local_repo_systemconfig(repo_dir, systemconfig):
    try:
        with open(os.path.join(repo_dir, 'systemconfig.yml'), 'w') as stream:
            stream.write('---\n')
            stream.write(yaml.dump(systemconfig, default_flow_style=False))
    except OSError as ex_file:
        get_logger().info(str(ex_file))


def repo_consistency_check(repo, console, git, local_repo_dir):

    local_url = git.remote_get_url_origin(local_repo_dir)

    if local_url != repo.url:
        console.printout(f' ! Different URL: {repo.url} != {local_url}')

    systemconfig = get_local_repo_systemconfig(local_repo_dir, console)
    env = None
    if systemconfig is None:
        systemconfig = dict()
        console.printout(f' ! Invalid systemconfig.yml: missing => COMP {repo.component} REL {repo.release}')
    else:
        env = systemconfig.get('env', None)
        if env is None:
            console.printout(f' ! Invalid systemconfig.yml: missing "env" => COMP {repo.component} REL {repo.release}')
        if not isinstance(env, dict):
            console.printout(f' ! Invalid systemconfig.yml: "env" is not a dictionary => COMP {repo.component} REL {repo.release}')
            env = None

    if env is None:
        env = dict()
        systemconfig['env'] = env
    else:
        comp = env.get('VCS_SAP_DELIVERY_COMP', None)
        if comp is None:
            console.printout(f' ! Invalid systemconfig.yml: missing "env.VCS_SAP_DELIVERY_COMP"')
        elif comp != repo.component:
            console.printout(f' ! Invalid systemconfig.yml: component mismatch {repo.component} != {comp}')

        rel = env.get('VCS_SAP_DELIVERY_RELEASE', None)
        if rel is None:
            console.printout(f' ! Invalid systemconfig.yml: missing "env.VCS_SAP_DELIVERY_RELEASE"')
        elif rel != repo.release:
            console.printout(f' ! Invalid systemconfig.yml: release mismatch {repo.release} != {rel}')

    return systemconfig



@DdciRepoGroup.argument('-n', '--dryrun', default=False, action='store_true')
@DdciRepoGroup.argument('destdir', default='/opt/ddci')
@DdciRepoGroup.command('synchronize')
# pylint: disable=unused-argument
def synchronize(connection, args):
    """Read repositories from an SAP system and clone them on a local FS"""

    console = sap.cli.core.get_console()

    mod_log().info('Creating the local dir: %s', args.destdir)
    os.makedirs(args.destdir, exist_ok=True)

    mod_log().info('Changing to the local dir: %s', args.destdir)
    os.chdir(args.destdir)

    local_dirs = get_local_repo_dirs(args.destdir)

    git = GitCommand(console)

    repos = fetch_ddci_repos(connection)
    not_clonable = list()
    checkout_error = list()

    for repo in repos:
        console.printout(f'* {repo.rid} -> {repo.url}')

        if repo.rid in local_dirs:
            mod_log().info('Already exists')
            local_dirs.remove(repo.rid)
            continue
        else:
            mod_log().info('Clonning')

            git.clone(repo.url, repo.rid)
            if git.proc.returncode != 0:
                console.printout(' ! Could not clone')
                continue

        local_repo_dir = os.path.join(args.destdir, repo.rid)

        mod_log().info('Checking out branch: %s', repo.branch)

        git.checkout(repo.branch, local_repo_dir)
        if git.proc.returncode != 0:
            console.printout(f' ! Could not checkout: {repo.branch}')
            checkout_error.append(repo)
            continue

        repo_consistency_check(repo, console, git, local_repo_dir)

    if local_dirs:
        console.printout('--- no longer gcts repos ---')
        for local_repo in local_dirs:
            console.printout(local_repo)

    return 0


@DdciRepoGroup.argument('-r', '--repo', default=None)
@DdciRepoGroup.argument('destdir', default='/opt/ddci')
@DdciRepoGroup.command()
# pylint: disable=unused-argument
def ddciproperties(connection, args):
    """Read jenkins/Jenkinsfile_CI and .ddci/properties.yml"""

    console = sap.cli.core.get_console()

    mod_log().info('Changing to the local dir: %s', args.destdir)
    os.chdir(args.destdir)

    local_dirs = get_local_repo_dirs(args.destdir)

    for repo in local_dirs:
        if args.repo is not None and repo != args.repo:
            continue

        console.printout(f'* {repo}')

        jenkisfile_ci = os.path.join(repo, 'jenkins', 'Jenkinsfile_CI')
        all_tokens = parse_jenkinsfile_ci(jenkisfile_ci)

        idx = 0
        tokens = [t for t in all_tokens if t.code != 'SP']

        jenkins_config_var = None
        jenkins_config = {}
        config_stash = []

        while idx < len(tokens):
            token = tokens[idx]
            idx += 1

            if token.value == 'def':
                identifier = tokens[idx]
                if identifier.code != 'WR':
                    mod_log().warning('The token "def" not followed by a "WR" token: %s %s', identifier.code, identifier.value)
                    continue

                assignop = tokens[idx+1]
                if assignop.value != '=':
                    mod_log().warning('The token "%s" not followed by assignment: %s %s', identifier.value, assignop.code, assignop.value)
                    continue

                openbrace = tokens[idx+2]
                if openbrace.value != '[':
                    mod_log().warning('The token "=" not followed by [: %s %s', openbrace.code, openbrace.value)
                    continue

                jenkins_config_var = identifier
                idx += 3
                config_stash.insert(0, jenkins_config)
                continue

            if config_stash:
                if token.value == ']':
                    config_stash.pop(0)

                if token.code == 'WR':
                    key = token.value

                    colon = tokens[idx]
                    if colon.value != ':':
                        mod_log().error('The config item "%s" not followed by ":": %s %s', key, colon.code, colon.value)
                        sys.exit(1)

                    value = tokens[idx+1]
                    if value.code == 'ST':
                        config_stash[0][key] = value.value[1:-2]
                    elif value.code == 'DG':
                        config_stash[0][key] = int(value.value)
                    elif value.code == 'BL':
                        config_stash[0][key] = bool(value.value)
                    elif value.value == '[':
                        new_config = {}
                        config_stash[0][key] = new_config
                        config_stash.insert(0, new_config)
                    else:
                        mod_log().error('The config item "%s" followed by an unexpected token: %s %s', key, value.code, value.value)
                        sys.exit(1)

                    idx += 2
                    continue

            if token.value == 'ddciPipelineAbapPackage':
                openbrace = tokens[idx]
                if openbrace.value != '(':
                    mod_log().warning('The token "ddciPipelineAbapPackage" not followed by "(": %s %s', openbrace.code, openbrace.value)
                    continue

                param = tokens[idx+1]
                if param.code != 'WR':
                    mod_log().warning('The token "ddciPipelineAbapPackage" not called with "%s": %s %s', jenparam.code, param.value)
                    sys.exit(1)

                closebrace = tokens[idx+2]
                if closebrace.value != ')':
                    mod_log().warning('The token "ddciPipelineAbapPackage" not closed by ")": %s %s', closerace.code, closerace.value)
                    continue

        print(yaml.dump(jenkins_config, default_flow_style=False))

    return 0


@DdciRepoGroup.argument('-n', '--dryrun', default=False, action='store_true')
@DdciRepoGroup.argument('destdir', default='/opt/ddci')
# pylint: disable=unused-argument
@DdciRepoGroup.command()
def jenkinsfiletoproperties(connection, args):
    """Transform jenkins/Jenkinsfile_CI to .ddci/properties.yml"""

    console = sap.cli.core.get_console()

    mod_log().info('Changing to the local dir: %s', args.destdir)
    os.chdir(args.destdir)

    local_dirs = get_local_repo_dirs(args.destdir)

    git = GitCommand(console)

    for repo in local_dirs:
        console.printout(f'* {repo}')

        jenkisfile_ci = os.path(repo, 'jenkins', 'Jenkinsfile_CI')
        jenkins = parse_jenkinsfile_ci(jenkisfile_ci)

    return 0


@DdciRepoGroup.argument('-n', '--dryrun', default=False, action='store_true')
@DdciRepoGroup.argument('destdir', default='/opt/ddci')
@DdciRepoGroup.command('migratetoer1')
# pylint: disable=unused-argument
def migratetoer1(connection, args):
    """Update SW Component, Release and other stuff for ER1"""

    component_mapping = {
        'SAPFCORE' : 'SAPSCORE_B',
        'SAPPCORE_H' : 'SAPPCORE_H',
        'SAPSCORE' : 'SAPSCORE_B',
        'SCORE_HOME' : 'SAPPCORE_H',
    }

    release_mapping  = {
        'S4DEV': 'S4DEV',
    }

    local_dirs = [entry.name for entry in os.scandir(args.destdir) if entry.is_dir(follow_symlinks=False)]
    console = sap.cli.core.get_console()
    git = GitCommand(console)
    repos = fetch_ddci_repos(connection)
    for repo in repos:
        console.printout(f'* {repo.rid} -> {repo.url}')
        if repo.rid not in local_dirs:
            console.printout(' ! - skipped')
            continue
        local_repo_dir = os.path.join(args.destdir, repo.rid)

        systemconfig = repo_consistency_check(repo, console, git, local_repo_dir)
        env = systemconfig['env']

        if repo.component == '':
            if repo.rid.startswith('s4corehome'):
                env['VCS_SAP_DELIVERY_COMP'] = 'SAPPCORE_H'
            else:
                env['VCS_SAP_DELIVERY_COMP'] = 'SAPSCORE_B'
        else:
            env['VCS_SAP_DELIVERY_COMP'] = component_mapping[repo.component]

        env['VCS_SAP_DELIVERY_RELEASE'] = release_mapping.get(repo.release, 'S4DEV')
        env['upload_system'] = 'ER1'
        env['upload_client'] = '001'

        if repo.branch == 'mirror_er9':
            git.checkout_new_local_branch('mirror_er1', local_repo_dir)

        write_local_repo_systemconfig(local_repo_dir, systemconfig)
        git.add('systemconfig.yml', local_repo_dir)
        git.commit('ddci: migrate to ER1 after CodeSplit', local_repo_dir)


@DdciRepoGroup.argument('-n', '--dryrun', default=False, action='store_true')
@DdciRepoGroup.argument('destdir', default='/opt/ddci')
@DdciRepoGroup.command('mirror')
# pylint: disable=unused-argument
def mirror(connection, args):
    """Create repositories from local filesystem in configure sap system"""

    console = sap.cli.core.get_console()

    local_dirs = [entry.name for entry in os.scandir(args.destdir) if entry.is_dir(follow_symlinks=False)]
    git = GitCommand(console)
    repos = fetch_ddci_repos(connection)
    repoidx = { repo.rid: repo for repo in repos }

    for repodir in local_dirs:
        local_repo_dir = os.path.join(args.destdir, repodir)
        local_url = git.remote_get_url_origin(local_repo_dir)

        console.printout(f'* {repodir} -> {local_url}')

        if repodir in repoidx:
            mod_log().info('Already exists')
            continue

        systemconfig = get_local_repo_systemconfig(local_repo_dir, console)
        if systemconfig is None:
            console.printout(f' ! systemconfig.yml: missing')
            continue

        mod_log().info('Setting up ...')
        new_repo = sap.rest.gcts.remote_repo.Repository(connection, repodir)

        mod_log().info('Creating ...')
        new_repo.create(
            local_url,
            '1ER',
            role='TARGET',
            typ='GITHUB',
            config={
                'VCS_NO_IMPORT': 'true',
                'VCS_TARGET_DIR': 'src/',
                'VCS_SAP_DELIVERY_COMP': systemconfig['env']['VCS_SAP_DELIVERY_COMP'],
                'VCS_SAP_DELIVERY_RELEASE': systemconfig['env']['VCS_SAP_DELIVERY_RELEASE'],
            }
        )

        mod_log().info('Clonning ...')
        new_repo.clone()

        current_branch = git.current_branch_name(local_repo_dir)
        if current_branch not in ['main', 'master']:
            mod_log().info('Checking out %s ...', current_branch)
            new_repo.checkout(current_branch)

        mod_log().info('Enabling imports ...')
        new_repo.set_config('VCS_NO_IMPORT', '')

        if current_branch not in ['main', 'master']:
            mod_log().info('Setting role SOURCE ...')
            new_repo.set_role('SOURCE')


    return 0


@DdciRepoGroup.command('check')
# pylint: disable=unused-argument
def check(connection, args):
    """ls"""

    ddci_repos = fetch_ddci_repos(connection)
    expected_branch = 'mirror_er9'

    repos = list()

    for repo in ddci_repos:
        if repo.role == 'SOURCE' and repo.branch != expected_branch:
            repos.append(repo)

    if repos:
        print('--------------------------------------------------------------------------------')
        print(f'# Change Role to TARGET or switch to the branch to {expected_branch}')
        print('--------------------------------------------------------------------------------')
        print_ddci_repolist(repos)
        print('--------------------------------------------------------------------------------')

    return 0


@DdciRepoGroup.argument('-n', '--dryrun', default=False, action='store_true')
@DdciRepoGroup.command('updatecomponents')
# pylint: disable=unused-argument
def updatecomponents(connection, args):
    """ls"""

    console = sap.cli.core.get_console()

    repos = fetch_ddci_repos(connection)
    for repo in repos:
        console.printout(f'* {repo.rid} -> {repo.url}')

        if repo.component:
            new_component = CS_COMPONENT_MAPPING[repo.component]
            if new_component == repo.component:
                console.printout(f' - OK: {repo.component}')
                continue

            console.printout(f' - {repo.component} -> {new_component}')

            if args.dryrun:
                continue

                repo.set_config('VCS_SAP_DELIVERY_COMP', args.value)


@DdciRepoGroup.argument('--adt-password', default=None)
@DdciRepoGroup.argument('--adt-user', default=None)
@DdciRepoGroup.argument('-c', '--commit', action='store_true', default=False)
@DdciRepoGroup.argument('destdir', default='/opt/ddci')
@DdciRepoGroup.command('analyze-packages')
# pylint: disable=unused-argument
def analyze_packages(connection, args):
    """Read packages of local FS repos and print them out"""

    adt_connection = sap.adt.Connection(
        args.ashost, args.client, args.adt_user, args.adt_password,
        port=args.port, ssl=args.ssl, verify=args.verify)

    layers = set()
    components = set()

    local_dirs = [entry.name for entry in os.scandir(args.destdir) if entry.is_dir(follow_symlinks=False)]
    for repodir in local_dirs:
        print(repodir)

        obj_dir = os.path.join(args.destdir, repodir, 'src/objects/DEVC')
        if not os.path.isdir(obj_dir):
            continue

        packages = [entry.name for entry in os.scandir(obj_dir) if entry.is_dir(follow_symlinks=False)]
        desync_pkgs = list()
        for pkg in packages:

            with open(os.path.join(obj_dir, pkg, f'DEVC {pkg}.asx.json'), 'r') as pkg_json:
                tables = json.loads(pkg_json.read())

            for t in tables:
                if t['table'] != 'TDEVC':
                    continue

                tdevc = t['data']
                break

            abap_pkg_name = tdevc[0]['DEVCLASS']
            component = tdevc[0]['DLVUNIT']
            layer = tdevc[0]['PDEVCLASS']

            try:
                adt_pkg = sap.adt.Package(adt_connection, abap_pkg_name)
                adt_pkg.fetch()

                syscomponent = adt_pkg.transport.software_component.name
                syslayer = adt_pkg.transport.transport_layer.name
            except:
                syscomponent = 'N/a'
                syslayer = 'N/a'

            if component != syscomponent or layer != layer:
                print(f'- {pkg:33}: {layer:6} :: {syslayer:6}; {component:10} :: {syscomponent}')
                desync_pkgs.append(abap_pkg_name)

            layers.add(layer)
            components.add(component)

        if args.commit and desync_pkgs:
            try:
                gcts_repo = sap.rest.gcts.remote_repo.Repository(connection, repodir)
                response = gcts_repo.commit('devc: update SW comp and TR layer',
                                      [{'object': pkg, 'type': 'DEVC'} for pkg in desync_pkgs],
                                      description='''We did not change the DEVC objects in repos during CodeSplit

JIRA=SYSDEV-888''',
                                      autopush=True)
                print(response)
            except Exception as ex:
                print(ex)

    print('---')
    print('layers')
    for l in layers:
        print(f'- {l}')

    print('components')
    for c in components:
        print(f'- {c}')
