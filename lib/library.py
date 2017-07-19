# Copyright (C) 2017  Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import datetime
import json
import os
import operator
import config from './config'


def get_houdini_environment_path(hou=None):
  hou = hou or config.get('houdinienv', 'houdini16.0')
  if not '/' in hou and not os.sep in hou:
    hou = os.path.expanduser('~/Documents/' + hou + '/houdini.env')
  return os.path.normpath(hou)


def get_houdini_user_prefs_directories():
  directory = os.path.expanduser('~/Documents')
  if not os.path.isdir(directory):
    return []
  result = []
  for name in os.listdir(directory):
    envfile = os.path.join(directory, name, 'houdini.env')
    if name.startswith('houdini') and os.path.isfile(envfile):
      result.append((name, envfile))
  result.sort(key=operator.itemgetter(0), reverse=True)
  return result


def install_library(env, directory, overwrite=False):
  # Open the librarie's configuration file.
  config_file = os.path.join(directory, 'houdini-library.json')
  if not os.path.isfile(config_file):
    raise NotALibraryError('missing library configuration file: {}'.format(config_file))
  with open(config_file) as fp:
    config = json.load(fp)

  now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
  version = module.package.json['version']

  # Initialize the default section. It's purpose is to make sure that
  # Houdini's default paths do not get messed up.
  section = env.get_named_section('DEFAULT')
  if not section:
    section = env.add_named_section('DEFAULT', '', before=env.get_first_named_section())
  else:
    section.clear()
  section.add_comment('  Automatically generated by houdini-manage v{}'.format(version))
  section.add_comment('  Last update: {}'.format(now))
  #for info in HOUDINI_PATH_ENVVARS:
  #  # Houdini will use the default value of the variable when it sees
  #  # the ampersand.
  #  section.add_variable(info['var'], '&')
  section.add_variable('HOUDINI_PATH', '&')
  section.add_variable('PYTHONPATH', '&')

  # Create or update the section for this library.
  directory = os.path.normpath(os.path.abspath(directory))
  section = env.get_named_section('library:' + config['libraryName'])
  if not section:
    previous = False
    section = env.add_named_section('library:' + config['libraryName'], '')
  else:
    previous = True
    if not overwrite:
      raise PreviousInstallationFoundError(config['libraryName'])

  section.clear()
  section.add_comment('  Automatically generated by houdini-manage v{}'.format(version))
  section.add_comment('  Last update: {}'.format(now))
  #for info in HOUDINI_PATH_ENVVARS:
  #  if not info['dir']: continue
  #  vardir = os.path.join(directory, info['dir'])
  #  if not os.path.isdir(vardir): continue
  #  section.add_variable(info['var'], '$' + info['var'], vardir)
  section.add_variable('HOUDINI_PATH', '$HOUDINI_PATH', directory)
  if os.path.isdir(os.path.join(directory, 'python')):
    section.add_variable('PYTHONPATH', '$PYTHONPATH', os.path.join(directory, 'python'))
  section.add_variable('HLIBPATH_' + config['libraryName'], directory)
  section.add_variable('HLIBVERSION_' + config['libraryName'], config['libraryVersion'])
  if config.get('environment'):
    section.add_comment('Environment variables specified by the library:')
    for line in config['environment']:
      section.add_line(line)


def remove_library(env, name):
  section = env.get_library(name)
  if section:
    env.remove_section(section)
    return True
  return False


class InstallError(Exception):
  pass

class NotALibraryError(InstallError):
  pass

class PreviousInstallationFoundError(InstallError):
  def __init__(self, library_name):
    self.library_name = library_name
