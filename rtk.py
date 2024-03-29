#!/bin/python3
from os import path
from string import Template
from glob import glob
from ruamel import yaml
import sys
import getopt

# config_file = 'config.yaml'
config_file = path.join(path.dirname(path.realpath(__file__)), 'config.yaml')
config_path = path.expandvars('$HOME/.config/rtk')
config_file = path.join(config_path, 'config.yaml')


class Config:
    def __init__(self, glob, name, infiles, outfile, active_set, **options):
        self.globals = glob
        self.name = name

        self.infiles = infiles
        self.outfile = outfile
        self.active_set = active_set
        self.options = options

    def export(self):
        out = {
                'name': self.name,
                'infiles': self.infiles,
                'outfile': self.outfile,
                'active_set': self.active_set
        }
        return dict(out, **self.options)

    def add_infile(self, filepath, fileset=None):
        if not fileset:
            fileset = self.active_set

        if not self.infiles:
            self.infiles = {}
        if not self.infiles.get(fileset):
            self.infiles[fileset] = []
        self.infiles[fileset].append(filepath)

    def del_infile(self, filepath, fileset=None):
        if not fileset:
            fileset = self.active_set

        try:
            self.infiles[fileset].remove(filepath)
        except ValueError:
            print(f'File {filepath} not in infiles of set {fileset}')

    def change_set(self, nfset):
        if nfset not in self.infiles.keys():
            print(f'Set {nfset} not found in {self.name}, creating new set')
        self.active_set = nfset

    # Load infiles, substitute variables and save to outfile
    def reconfigure(self):
        out_str = ""
        try:
            infiles = self.infiles[self.active_set]
        except TypeError:
            print(f'Ignoring {self.name}, set {self.active_set} not found')
            return

        # Handle glob string
        if infiles == None:
            infiles = []
        elif type(infiles) == str:
            infiles = [infiles]

        for fn in infiles:
            fn = path.abspath(fn)
            if not path.exists(fn):
                # Handle glob inside of list
                infiles += (sorted(glob(fn)))
            else:
                # Load file
                print(f'Concatenating {fn}')
                with open(fn, 'r') as f:
                    out_str += f.read()

        # Substituting variables
        if self.globals['substitution'].get('default', False) or \
           self.options.get('substitute', False):
            basepath = self.globals['substitution']['basepath']
            if not path.isdir(basepath):
                basepath = path.join(config_path, basepath)
            with open(
                    path.join(basepath,self.globals['substitution']['source']),
                    'r') as f:
                sub_source = yaml.safe_load(f)
                out_str = Template(out_str).safe_substitute(
                            **sub_source)

        if not out_str:
            # Prevent nuking config file
            print(f'Ignoring {self.name}, no infiles read (files not found?)')
            return 

        # Saving out_str to outfile
        outfile = self.outfile
        if outfile:
            print(f'Saving to {outfile}')
            with open(outfile, 'w') as f:
                f.write(out_str)


class ConfigsHandler:
    def __init__(self, config_file='config.yaml'):
        self.load_config_file(config_file)

    # Go over all configs
    def reconfigure_configs(self):
        for config in self.configs.values():
            config.reconfigure()

    def get_config(self, name):
        out = None
        try:
            out = self.configs[name]
        except KeyError:
            print(f'Config name {name} not found')
        return out
    
    def init_config(self, name:str, outfile):
        print(outfile)
        self.configs[name] = Config(self.globals, name, None, outfile, 'default')

    def load_config_file(self, config_file):
        with open(config_file, 'r') as f:
            self.__config = yaml.load(f.read(), Loader=yaml.RoundTripLoader)

            self.globals = {}
            self.globals['substitution'] = self.__config['substitution']

            self.configs = {}
            if self.__config['configs']:
                for config in self.__config['configs']:
                    self.configs[config['name']] = Config(self.globals, **config)

    def dump_config_file(self, out_file):
        out = self.__config.copy()
        out['configs'] = [ c.export() for c in self.configs.values() ]

        with open(out_file, 'w') as f:
            yaml.dump(out, f, default_flow_style=False, indent=4, Dumper=yaml.RoundTripDumper)

    def print_all(self):
        for name in self.configs.keys():
            self.print(name)

    def print(self, name):
        pad = ' '*4

        config = self.configs.get(name)

        if config:
            print(f'{name}:')
            print(f'{pad}infiles:')
            for fileset, infiles in config.infiles.items():
                print(f'{pad}{pad}{fileset}: {infiles}')
            print(f'{pad}outfile: {config.outfile}')
            print(f'{pad}active_set: {config.active_set}')
            print()
        else:
            print(f'No config {name} available')

    def print_configs(self):
        for config in self.configs.keys():
            print(f'- {config}')

actions = ['list', 'reconfigure', 'init', 'add', 'set', 'delete']

def print_exit(msg):
    print(msg)
    sys.exit(1)

def print_usage():
    print('Usage: {} [-c config.yaml] action [config] [option]'.format(
        path.basename(sys.argv[0])))
    print('Default rtk config path:', config_file)
    print('Valid actions are:', ', '.join(actions))
    sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print_usage()

    opts, args = getopt.getopt(sys.argv[1:], 'c:', ['config='])
    for opt, arg in opts:
        if opt in ('-c', '--config'):
            config_file = arg

    cfgh = ConfigsHandler(config_file=config_file)

    if args[0] not in actions:
        print(f'Invalid action: {args[0]}')
        print_usage()

    # Options not needing config name as argument
    if args[0] in ('list', 'l'):
        if len(args) > 1:
            cfgh.print(args[1])
        else:
            cfgh.print_all()
    elif args[0]in ('reconfigure', 'reconf', 'r'):
        print('Combining infiles, replacing variables and exporting to outfile for all configs')
        cfgh.reconfigure_configs()
    else:
        # Options needing config name as argument
        if len(args) < 2:
            cfgh.print_configs()
            print_exit('Missing config name to use')

        if args[0] in ('init'):
            if len(args) < 3:
                print('Initialize new config')
                print_exit('Missing outfile path')

            cfgh.init_config(args[1], path.realpath(args[2]))
            print(f'{args[1]} initialized with outfile {path.realpath(args[2])}')

        elif args[0] in ('add', 'a'):
            config = cfgh.get_config(args[1])

            if len(args) < 3:
                print(f'Add infile to currently active set: {config.active_set}')
                print_exit('Missing infile to add')

            config.add_infile(path.realpath(args[2]))
            print(f'infile {path.realpath(args[2])} added to set {config.active_set}')
        elif args[0] in ('set', 's'):
            config = cfgh.get_config(args[1])

            if len(args) < 3:
                new = True
                for fset in config.infiles.keys():
                    if config.active_set == fset:
                        print(f'- [{fset}]')
                        new = False
                    else:
                        print(f'- {fset}')
                if new: print(f'Creating new set: {config.active_set}')
                print_exit('Missing set to change to')

            config.change_set(args[2])
            print(f'Active set of {args[1]} set to {args[2]}')
        elif args[0] in ('delete', 'del', 'd'):
            config = cfgh.get_config(args[1])

            if len(args) < 3:
                print(f'Delete infile from currently active set: {config.active_set}')
                print_exit('Missing infile to remove')

            config.del_infile(path.realpath(args[2]))
            print(f'Removed {args[2]} from set {config.active_set} of {config.name}')


    cfgh.dump_config_file(config_file)
