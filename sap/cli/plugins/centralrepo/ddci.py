"""gCTS methods"""

import os
import yaml
import json

from sap import get_logger
import sap.cli.core
import sap.cli.helpers
import sap.rest.gcts.simple
from sap.rest.gcts.remote_repo import Repository

from sap.cli.plugins.centralrepo.git import (
    get_local_repo_dirs,
    GitCommand
)

from sap.cli.plugins.centralrepo.jenkinsfile import (
    parse_jenkinsfile_ci,
    evaulate_ddci_pipeline_config
)

from sap.rest.gcts.sugar import (
    abap_modifications_disabled
)

from sap.rest.gcts.errors import (
    GCTSRequestError,
    SAPCliError,
)

from sap.cli.gcts import (
    dump_gcts_messages,
    ConsoleSugarOperationProgress
)

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


def load_yaml_file(filepath, console):
    try:
        with open(filepath, 'r') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as ex_yaml:
                console.printerr(str(ex_yaml))
    except OSError as ex_file:
        get_logger().info(str(ex_file))

    return None


def get_local_repo_systemconfig(repo_dir, console):
    return load_yaml_file(os.path.join(repo_dir, 'systemconfig.yml'), console)

def get_ddci_properties(repo_dir, console):
    return load_yaml_file(os.path.join(repo_dir, '.ddci', 'properties.yml'), console)

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
        jenkins_config, _, __ = evaulate_ddci_pipeline_config(all_tokens)

        print(yaml.dump(jenkins_config, default_flow_style=False))

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


@DdciRepoGroup.argument('-r', '--repo')
@DdciRepoGroup.argument('-c', '--commit')
@DdciRepoGroup.argument('-b', '--branch')
@DdciRepoGroup.argument('destdir', default='/opt/ddci')
@DdciRepoGroup.command('pull_ddci_configuration_changes_commit')
# pylint: disable=unused-argument
def pull_ddci_configuration_changes_commit(connection, args):
    """Pull central mirror branch with remote mirror branch"""

    gcts_repos = sap.rest.gcts.simple.fetch_repos(connection)

    for gcts_repo in gcts_repos:
        if gcts_repo.name != args.repo:
            continue
            
        mod_log().info('Repo: %s', gcts_repo.name)
        central_repo_branch = gcts_repo.branch
        mod_log().info('Branch on central repo: %s', central_repo_branch)
        central_repo_head_commit_hash = gcts_repo.head
        mod_log().info('Last commit on central repo branch: %s', central_repo_head_commit_hash)

        if central_repo_branch != args.branch:
            print("ERROR: Branch of central gCTS repo is not " + args.branch + "!")
            exit(2)
        
        console = sap.cli.core.get_console()
        git = GitCommand(console)
        local_repo_dir = os.path.join(args.destdir, gcts_repo.rid)
        
        remote_repo_url = git.remote_get_url_origin(local_repo_dir).removesuffix(".git")
        gcts_repo_url_without_suffix = gcts_repo.url.removesuffix(".git")
        if remote_repo_url != gcts_repo_url_without_suffix:
            print("ERROR:   Remote URL of local GIT repository in given destination doesn't match with repository URL of the central one")
            print("Central: " + gcts_repo_url_without_suffix)
            print("Local:   " + remote_repo_url)
            exit(1)
        local_repo_branch = git.current_branch_name(local_repo_dir)
        if local_repo_branch != central_repo_branch:
            print("ERROR:   Local repository branch doesn't match with branch of the central one")
            print("Central: " + central_repo_branch)
            print("Local:   " + local_repo_branch)
            exit(1)
        local_repo_commit = git.run('rev-parse', 'HEAD', cwd=local_repo_dir)
        if local_repo_commit != args.commit:
            print("ERROR:   Local repository HEAD commit hash doesn't match with branch of the central one")
            print("Central: " + central_repo_head_commit_hash)
            print("Local:   " + local_repo_commit)
            exit(1)
        
        difference_commits = git.run('cherry', central_repo_head_commit_hash, cwd=local_repo_dir)
        mod_log().info('Difference commits between central repo branch and remote repo branch:')
        mod_log().info(difference_commits)
        
        if difference_commits == '':
            print("WARNING: Remote " + args.branch + " branch and central gCTS " + central_repo_branch + " branch are equal. Nothing to pull.")
            exit(0)
        
        list_of_difference_commits = difference_commits.splitlines()
        # example of print(list_of_difference_commits):
        # + fac6af5dd8ae6e399e937dba6f4d31be7654d833
        # + 7c9762c19b70afedf2c1bf583af3793f6fa3cf93
        if len(list_of_difference_commits) != 1:
            print("ERROR:    The difference between remote " + args.branch + " branch and central gCTS " + central_repo_branch + " branch should be just one commit")
            print("Expected: " + args.commit)
            print("Actual:   " + difference_commits)
            exit(3)
        hash_of_first_commit = list_of_difference_commits[0].split()[1]
        mod_log().info('Commit hash of first difference: %s', hash_of_first_commit)
        if hash_of_first_commit != args.commit:
            print("ERROR:    The difference between remote " + args.branch + " branch and central gCTS " + args.branch + " branch should be just one concrete commit")
            print("Expected: " + args.commit)
            print("Actual:   " + hash_of_first_commit)
            exit(4)
        
        print("The difference between remote " + args.branch + " branch and central gCTS " + args.branch + " branch is only following commit:")
        print(hash_of_first_commit)
        print("")
        
        noimports_progress = ConsoleSugarOperationProgress(console)
        try:
            with abap_modifications_disabled(gcts_repo, progress=noimports_progress):
                print('Pulling central GCTS repo ...')
                response = sap.rest.gcts.simple.pull(connection, gcts_repo.name)
                print(response)
        except GCTSRequestError as ex:
            dump_gcts_messages(console, ex.messages)
            exit(1)
        except SAPCliError as ex:
            console.printerr(str(ex))
            exit(1)
