import re
import os
import shutil
import subprocess
from io import StringIO

from sap import get_logger


def mod_log():
    """ADT Module logger"""

    return get_logger()


def get_local_repo_dirs(basedir):
    return [entry.name for entry in os.scandir(basedir) if entry.is_dir(follow_symlinks=False)]


class GitCommand:

    def __init__(self, console):
        self._git_bin = shutil.which('git')
        self.proc = None
        self._console = console

    def run(self, *args, cwd=None, stdin=None):
        _args = [self._git_bin]
        _args.extend(args)
        mod_log().info('Executing: %s', str(_args))
        process_stdin = None
        if stdin is not None:
            process_stdin = subprocess.PIPE
            stdin = stdin.encode()

        self.proc = subprocess.Popen(_args, cwd=cwd, stdin=process_stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            outs, errs = self.proc.communicate(input=stdin, timeout=600)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            outs, errs =self.proc.communicate()

        if self.proc.returncode != 0:
            get_logger().info(errs.decode('utf-8'))

        return outs.decode('utf-8').strip()

    def remote_get_url_origin(self, repo_dir):
        url =  self.run('remote', 'get-url', 'origin', cwd=repo_dir)

        if url is not None:
            url = re.sub('https://.*github\\.', 'https://github.', url)

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
        if message_body is None:
            return self.run('commit', '-m', message, cwd=repo_dir)
        else:
            stdin = f'{message}\n\n{message_body}'
            return self.run('commit', '-F-', cwd=repo_dir, stdin=stdin)

    def current_branch_name(self, repo_dir):
        return self.run('branch', '--show-current', cwd=repo_dir)
