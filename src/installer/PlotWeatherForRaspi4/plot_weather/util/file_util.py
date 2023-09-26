import json
import os


def gen_imgname(script_filename, dot_ext='.png'):
    return os.path.basename(script_filename).replace('.py', dot_ext)


def read_json(file):
    with open(file, 'r') as fp:
        data = json.load(fp)
    return data


def save_text(file, contents):
    with open(file, 'w') as fp:
        fp.write(contents)
