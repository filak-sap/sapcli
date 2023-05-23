"""gCTS methods"""

import os
import shutil
import subprocess
import yaml

from sap import get_logger
import sap.cli.core
import sap.cli.helpers
import sap.rest.gcts.simple
from sap.rest.gcts.remote_repo import Repository


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
        ('name', 'Name')
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

    def run(self, *args, cwd=None):
        _args = [self._git_bin]
        _args.extend(args)
        self.proc = subprocess.Popen(_args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            outs, errs = self.proc.communicate(timeout=60)
        except TimeoutExpired:
            self.proc.kill()
            outs, errs =self.proc.communicate()

        if self.proc.returncode != 0:
            get_logger().info(errs.decode('utf-8'))

        return outs.strip()

    def remote_get_url_origin(self, repo_dir):
        return self.run('remote', 'get-url', 'origin', cwd=repo_dir)

    def clone(self, url, dirname):
        return self.run('clone', url, dirname)

    def checkout(self, branch, repo_dir):
        return self.run('checkout', branch, cwd=repo_dir)


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


@DdciRepoGroup.argument('-n', '--dryrun', default=False, action='store_true')
@DdciRepoGroup.argument('destdir', default='/opt/ddci')
@DdciRepoGroup.command('synchronize')
# pylint: disable=unused-argument
def synchronize(connection, args):
    """ls"""

    component_mapping = {
        'S4CORE' : '',
        'SAPFCORE' : '',
        'SAPPCORE_H' : '',
        'SAPSCORE' : '',
        'SCORE_HOME' : '',
    }
    release_mapping  = {
        '107': '',
        'S4DEV': '',
    }

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
    missing_systemconfing = list()

    for repo in repos:
        console.printout(f'* {repo.rid} -> {repo.url}')

        if repo.rid in local_dirs:
            mod_log().info('Already exists')
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

        local_url = git.remote_get_url_origin(local_repo_dir)

        if local_url == repo.url:
            console.printout(f' ! Different URL: {repo.url} != {local_url}')

        systemconfig = get_local_repo_systemconfig(local_repo_dir, console)
        env = None
        if systemconfig is None:
            systemconfig = dict()
            missing_systemconfing.append(repo)
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

        env['VCS_SAP_DELIVERY_COMP'] = component_mapping.get(repo.component, 'S4CORE')
        env['VCS_SAP_DELIVERY_RELEASE'] = release_mapping.get(repo.release, 'S4DEV')
        env['upload_system'] = 'ER1'
        env['upload_client'] = '001'

        console.printout(yaml.dump(systemconfig, default_flow_style=False))


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

