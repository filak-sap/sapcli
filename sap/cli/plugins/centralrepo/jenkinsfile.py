import sys
import typing
from enum import Enum


SPACE = ' \t\r\n'
QUOTES = '\'"'
OPERATORS = '=[]:,()'


class State(Enum):
    CODE = 0
    STRING = 1


class Token(typing.NamedTuple):
    code: str
    value: str


def parse_jenkinsfile_ci(filepath):

    print('Analyzing:', filepath)
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
                token = contents[pos:cursor+1]
                tokens.append(Token('ST', token))
                pos = cursor + 1

        if delim_typ is not None:
            if pos != cursor:
                token = contents[pos:cursor]
                if token.isdigit():
                    tokens.append(Token('DG', token))
                elif token.lower() in ['true', 'false']:
                    tokens.append(Token('BL', token))
                else:
                    tokens.append(Token('WR', token))

            tokens.append(Token(delim_typ, symbol))

            pos = cursor + 1

        cursor += 1

    return tokens


if __name__ == "__main__":
    tokens = parse_jenkinsfile_ci(sys.argv[1])

    for token in tokens:
        if token.code == 'SP':
            continue

        print(token.code, token.value)

