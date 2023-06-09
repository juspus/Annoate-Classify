﻿import os
import subprocess
import sys

from subprocess import CalledProcessError
from typing import List, Dict, Optional

import pkg_resources
from dacite import from_dict, ForwardReferenceError, UnexpectedDataError, WrongTypeError, MissingValueError
from pkg_resources import Distribution

from model import PluginConfig, DependencyModule
from util import FileSystem


class PluginUtility:
    __IGNORE_LIST = ['__pycache__']

    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    def __filter_unwanted_directories(name: str) -> bool:
        return not PluginUtility.__IGNORE_LIST.__contains__(name)

    @staticmethod
    def filter_plugins_paths(plugins_package) -> List[str]:
        """
        filters out a list of unwanted directories
        :param plugins_package:
        :return: list of directories
        """
        return list(
            filter(
                PluginUtility.__filter_unwanted_directories,
                os.listdir(plugins_package)
            )
        )

    @staticmethod
    def __get_missing_packages(
            installed: List[Distribution],
            required: Optional[List[DependencyModule]]
    ) -> List[DependencyModule]:
        missing = list()
        if required is not None:
            installed_packages: List[str] = [
                pkg.project_name for pkg in installed]
            for required_pkg in required:
                if not installed_packages.__contains__(required_pkg.name):
                    missing.append(required_pkg)
        return missing

    def __manage_requirements(self, package_name: str, plugin_config: PluginConfig):
        installed_packages: List[Distribution] = list(
            filter(lambda pkg: isinstance(pkg, Distribution),
                   pkg_resources.working_set)
        )
        missing_packages = self.__get_missing_packages(
            installed_packages, plugin_config.requirements)
        for missing in missing_packages:

            python = sys.executable
            exit_code = subprocess.check_call(
                [python, '-m', 'pip', 'install', missing.__str__()],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

    def __read_configuration(self, module_path) -> Optional[PluginConfig]:

        plugin_config_data = FileSystem.load_configuration(
            'plugin.yaml', module_path)
        plugin_config = from_dict(
            data_class=PluginConfig, data=plugin_config_data)
        return plugin_config

    def setup_plugin_configuration(self, package_name, module_name) -> Optional[str]:
        """
        Handles primary configuration for a give package and module
        :param package_name: package of the potential plugin
        :param module_name: module of the potential plugin
        :return: a module name to import
        """
        # if the item has not folder we will assume that it is a directory
        module_path = os.path.join(
            FileSystem.get_plugins_directory(), module_name)
        if os.path.isdir(module_path):
            plugin_config: Optional[PluginConfig] = self.__read_configuration(
                module_path)
            if plugin_config is not None:
                self.__manage_requirements(package_name, plugin_config)
                return plugin_config.runtime.main, plugin_config
        return None
