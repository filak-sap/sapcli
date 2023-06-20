"""gCTS methods"""

import os
from io import StringIO
import shutil
import subprocess
import re
import yaml

from sap import get_logger
import sap.cli.core
import sap.cli.helpers
import sap.rest.gcts.simple
from sap.rest.gcts.remote_repo import Repository

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


def get_local_repo_systemconfig(repo_dir, console):
    try:
        with open(os.path.join(repo_dir, 'systemconfig.yml'), 'r') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLERROR as ex_yaml:
                console.printerr(str(ex_yaml))
    except OSError as ex_file:
        get_logger().info(str(ex_file))

    return None


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
    """ls"""

    console = sap.cli.core.get_console()

    mod_log().info('Creating the local dir: %s', args.destdir)
    os.makedirs(args.destdir, exist_ok=True)

    mod_log().info('Changing to the local dir: %s', args.destdir)
    os.chdir(args.destdir)

    local_dirs = [entry.name for entry in os.scandir(args.destdir) if entry.is_dir(follow_symlinks=False)]

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

@DdciRepoGroup.argument('-n', '--dryrun', default=False, action='store_true')
@DdciRepoGroup.argument('destdir', default='/opt/ddci')
@DdciRepoGroup.command('migratetoer1')
# pylint: disable=unused-argument
def migratetoer1(connection, args):
    """ls"""

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
    """ls"""

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
