
import os, sys, shutil
import subprocess
import platform
import distro

from .utils import pj, download_remote, escape_path
from ._global import neutralEnv, option


class PlatformNeutralEnv:
    def __init__(self):
        self.working_dir = option('working_dir')
        self.source_dir = pj(self.working_dir, "SOURCE")
        self.archive_dir = pj(self.working_dir, "ARCHIVE")
        self.toolchain_dir = pj(self.working_dir, "TOOLCHAINS")
        self.log_dir = pj(self.working_dir, 'LOGS')
        for d in (self.source_dir,
                  self.archive_dir,
                  self.toolchain_dir,
                  self.log_dir):
            os.makedirs(d, exist_ok=True)
        self.detect_platform()
        self.ninja_command = self._detect_command(
            'ninja',
            default=[['ninja'], ['ninja-build']])
        self.meson_command = self._detect_command(
            'meson',
            default= [['meson.py'], ['meson']])
        self.mesontest_command = [*self.meson_command, "test"]
        self.patch_command = self._detect_command('patch')
        self.git_command = self._detect_command('git')
        self.make_command = self._detect_command('make')
        self.cmake_command = self._detect_command('cmake')
        self.qmake_command = self._detect_command('qmake', required=False)


    def detect_platform(self):
        _platform = platform.system()
        self.distname = _platform
        if _platform == 'Windows':
            print('ERROR: kiwix-build is not intented to run on Windows platform.\n'
                  'It should probably not work, but well, you still can have a try.')
            cont = input('Do you want to continue ? [y/N]')
            if cont.lower() != 'y':
                sys.exit(0)
        if _platform == 'Linux':
            self.distname = distro.id()
            if self.distname == 'ubuntu':
                self.distname = 'debian'

    def download(self, what, where=None):
        where = where or self.archive_dir
        download_remote(what, where)


    def _detect_command(self, name, default=None, options=['--version'], required=True):
        if default is None:
            default = [[name]]
        env_key = 'KBUILD_{}_COMMAND'.format(name.upper())
        if env_key in os.environ:
            default = [os.environ[env_key].split()] + default
        for command in default:
            try:
                retcode = subprocess.check_call(command + options,
                                                stdout=subprocess.DEVNULL)
            except (FileNotFoundError, PermissionError, OSError):
                # Doesn't exist in PATH or isn't executable
                continue
            if retcode == 0:
                return command
        else:
            if required:
                sys.exit("ERROR: {} command not found".format(name))
            else:
                print("WARNING: {} command not found".format(name))
                return ["{}_NOT_FOUND".format(name.upper())]

class BuildEnv:
    def __init__(self, platformInfo):
        build_dir = "BUILD_{}".format(platformInfo.name)
        self.platformInfo = platformInfo
        self.base_build_dir = pj(option('working_dir'), option('build_dir'))
        self.build_dir = pj(self.base_build_dir, build_dir)
        self.install_dir = pj(self.build_dir, "INSTALL")
        self.toolchain_dir = pj(self.build_dir, "TOOLCHAINS")
        self.log_dir = pj(self.build_dir, 'LOGS')
        for d in (self.build_dir,
                  self.install_dir,
                  self.toolchain_dir,
                  self.log_dir):
            os.makedirs(d, exist_ok=True)

        self.libprefix = option('libprefix') or self._detect_libdir()

    def clean_intermediate_directories(self):
        for subdir in os.listdir(self.build_dir):
            subpath = pj(self.build_dir, subdir)
            if subpath == self.install_dir:
                continue
            if os.path.isdir(subpath):
                shutil.rmtree(subpath)
            else:
                os.remove(subpath)

    def _is_debianlike(self):
        return os.path.isfile('/etc/debian_version')

    def _detect_libdir(self):
        if self.platformInfo.libdir is not None:
            return self.platformInfo.libdir
        if self._is_debianlike():
            try:
                pc = subprocess.Popen(['dpkg-architecture', '-qDEB_HOST_MULTIARCH'],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL)
                (stdo, _) = pc.communicate()
                if pc.returncode == 0:
                    archpath = stdo.decode().strip()
                    return 'lib/' + archpath
            except Exception:
                pass
        if os.path.isdir('/usr/lib64') and not os.path.islink('/usr/lib64'):
            return 'lib64'
        return 'lib'

    def get_env(self, *, cross_comp_flags, cross_compilers, cross_path):
        env = self.platformInfo.get_env()
        pkgconfig_path = pj(self.install_dir, self.libprefix, 'pkgconfig')
        env['PKG_CONFIG_PATH'] = ':'.join([env['PKG_CONFIG_PATH'], pkgconfig_path])

        env['PATH'] = ':'.join([
            escape_path(pj(self.install_dir, 'bin')),
            env['PATH']
        ])

        env['LD_LIBRARY_PATH'] = ':'.join([env['LD_LIBRARY_PATH'],
                                          pj(self.install_dir, 'lib'),
                                          pj(self.install_dir, self.libprefix)
                                          ])

        env['QMAKE_CXXFLAGS'] = " ".join([
            escape_path('-I'+pj(self.install_dir, 'include')),
            env['QMAKE_CXXFLAGS']
        ])
        env['CPPFLAGS'] = " ".join([
            escape_path('-I'+pj(self.install_dir, 'include')),
            env['CPPFLAGS']
        ])
        env['QMAKE_LFLAGS'] = " ".join([
            escape_path('-L'+pj(self.install_dir, 'lib')),
            escape_path('-L'+pj(self.install_dir, self.libprefix)),
            env['QMAKE_LFLAGS']
        ])
        env['LDFLAGS'] = " ".join([
            escape_path('-L'+pj(self.install_dir, 'lib')),
            escape_path('-L'+pj(self.install_dir, self.libprefix)),
            env['LDFLAGS']
        ])

        if cross_comp_flags:
            self.platformInfo.set_comp_flags(env)
        if cross_compilers:
            self.platformInfo.set_compiler(env)
        if cross_path:
            env['PATH'] = ':'.join(self.platformInfo.get_bin_dir() + [env['PATH']])
        return env


    @property
    def configure_wrapper(self):
        try:
            yield self.platformInfo.configure_wrapper
        except AttributeError:
            pass

    @property
    def make_wrapper(self):
        try:
            yield self.platformInfo.make_wrapper
        except AttributeError:
            pass
