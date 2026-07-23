import sys
import typing
from enum import Enum

from sap import get_logger


SPACE = ' \t\r\n'
QUOTES = '\'"'
OPERATORS = '=[]:,()'


def mod_log():
    """ADT Module logger"""

    return get_logger()


class State(Enum):
    CODE = 0
    STRING = 1


class Token(typing.NamedTuple):
    code: str
    value: str
    pos: int


def parse_jenkinsfile_ci(filepath):

    with open(filepath, 'r') as filestream:
        # @Library()
        # def config = [ general: [] , stages: [foo: [] ] , ... ]
        # ddciPipelineAbapPackage(config)
        contents = filestream.read()

    tokens = []
    state = State.CODE
    pos = 0
    cursor = 0
    while cursor < len(contents):
        symbol = contents[cursor]

        delim_typ = None

        # We are either in CODE or in STRING
        if state == State.CODE:
            if symbol in OPERATORS:
                delim_typ = 'OP'
            elif symbol in SPACE:
                delim_typ = 'SP'
        # else we are currently parsing a string literal

        if symbol in QUOTES:
            if state == State.CODE:
                # We go an opening Quote
                state = State.STRING
            elif state == State.STRING:
                # We go a closing Quote -> !!! If they escape, then we got this wrong !!!
                state = State.CODE
                token = contents[pos:cursor + 1]
                tokens.append(Token('ST', token, len(tokens)))
                pos = cursor + 1

        if delim_typ is not None:
            if pos != cursor:
                token = contents[pos:cursor]
                if token.isdigit():
                    tokens.append(Token('DG', token, len(tokens)))
                elif token.lower() in ['true', 'false']:
                    tokens.append(Token('BL', token, len(tokens)))
                else:
                    tokens.append(Token('WR', token, len(tokens)))

            tokens.append(Token(delim_typ, symbol, len(tokens)))

            pos = cursor + 1

        cursor += 1

    return tokens


def evaulate_ddci_pipeline_config(all_tokens):
    idx = 0
    tokens = [t for t in all_tokens if t.code != 'SP']

    jenkins_config_var = None
    jenkins_config = {}
    config_stash = []

    first_token = None
    last_token = None

    while idx < len(tokens):
        token = tokens[idx]
        idx += 1

        if token.value == 'def':
            identifier = tokens[idx]
            if identifier.code != 'WR':
                mod_log().warning('The token "def" not followed by a "WR" token: %s %s', identifier.code, identifier.value)
                continue

            assignop = tokens[idx + 1]
            if assignop.value != '=':
                mod_log().warning('The token "%s" not followed by assignment: %s %s', identifier.value, assignop.code, assignop.value)
                continue

            openbrace = tokens[idx + 2]
            if openbrace.value != '[':
                mod_log().warning('The token "=" not followed by [: %s %s', openbrace.code, openbrace.value)
                continue

            jenkins_config_var = identifier
            first_token = token.pos
            idx += 3
            config_stash.insert(0, jenkins_config)
            continue

        if config_stash:
            if token.value == ']':
                config_stash.pop(0)
                if not config_stash:
                    last_token = token.pos

            if token.code == 'WR':
                key = token.value

                colon = tokens[idx]
                if colon.value != ':':
                    mod_log().error('The config item "%s" not followed by ":": %s %s', key, colon.code, colon.value)
                    sys.exit(1)

                value = tokens[idx + 1]
                if value.code == 'ST':
                    config_stash[0][key] = value.value[1:-1]
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

        if token.value == 'ddciPipelineAbapPackage' and jenkins_config_var:
            openbrace = tokens[idx]
            if openbrace.value != '(':
                mod_log().warning('The token "ddciPipelineAbapPackage" not followed by "(": %s %s', openbrace.code, openbrace.value)
                continue

            param = tokens[idx + 1]
            if param.code != 'WR':
                mod_log().warning('The token "ddciPipelineAbapPackage" not called with "%s": %s %s', param.code, param.value)
                sys.exit(1)

            closebrace = tokens[idx + 2]
            if closebrace.value != ')':
                mod_log().warning('The token "ddciPipelineAbapPackage" not closed by ")": %s %s', closebrace.code, closebrace.value)
                continue

    return (jenkins_config, first_token, last_token)


if __name__ == "__main__":
    tokens = parse_jenkinsfile_ci(sys.argv[1])

    for token in tokens:
        if token.code == 'SP':
            continue

        print(token.code, token.value)
