﻿import os
from importlib import import_module
from typing import List, Any, Dict

from engine import IPluginRegistry, AnnotationPluginCore
from engine.engine_contract import FilterPluginCore
from model import PluginConfig, AnnotationAgent
from model.models import FilterAgent, FilterAgentRequiredAnnotationAgent
from PySimpleGUI import PySimpleGUI as sg
from .utilities import PluginUtility


class PluginUseCase:
    annotation_modules: List[type]
    filter_modules: List[type]

    def __init__(self) -> None:
        self.plugins_package: str = 'Plugins'
        self.plugin_util = PluginUtility()
        self.annotation_modules = list()
        self.filter_modules = list()

    def __check_loaded_plugin_state(self, plugin_module: Any, config: PluginConfig):
        if len(IPluginRegistry.plugin_registries) > 0:
            latest_module = IPluginRegistry.plugin_registries[-1]
            latest_module_name = latest_module.__module__
            current_module_name = plugin_module.__name__
            if current_module_name == latest_module_name:
                if config.annotation_agent:
                    if AnnotationAgent.select().where(AnnotationAgent.alias == config.alias).count() == 0:
                        AnnotationAgent.create(name=config.name, alias=config.alias, creator=config.creator,
                                               repository=config.repository, description=config.description, version=config.version)
                    self.annotation_modules.append(latest_module)
                else:
                    if FilterAgent.select().where(FilterAgent.alias == config.alias).count() == 0:
                        fa = FilterAgent.create(name=config.name, alias=config.alias, creator=config.creator,
                                                repository=config.repository, description=config.description, version=config.version)

                        for reqAgent in config.required_agents:
                            aas = AnnotationAgent.select().where(
                                AnnotationAgent.alias == reqAgent)
                            if aas.count() == 0:
                                FilterAgent.delete_by_id(fa.id)
                                sg.PopupOK(
                                    f'Make sure annotation agents {config.required_agents} are installed. Restart may be needed.')
                                continue
                            aa = aas[0]
                            FilterAgentRequiredAnnotationAgent.create(
                                filter_agent=fa, annotation_agent=aa)

                    self.filter_modules.append(latest_module)
            IPluginRegistry.plugin_registries.clear()

    def __search_for_plugins_in(self, plugins_path: List[str], package_name: str):
        for directory in plugins_path:
            entry_point, config = self.plugin_util.setup_plugin_configuration(
                package_name, directory)
            if entry_point is not None:
                plugin_name, plugin_ext = os.path.splitext(entry_point)
                # Importing the module will cause IPluginRegistry to invoke it's __init__ fun
                import_target_module = f'.{directory}.{plugin_name}'
                module = import_module(import_target_module, package_name)
                self.__check_loaded_plugin_state(module, config)
            else:
                self._logger.debug(f'No valid plugin found in {package_name}')

    def discover_plugins(self, reload: bool):
        """
        Discover the plugin classes contained in Python files, given a
        list of directory names to scan.
        """
        if reload:
            self.annotation_modules.clear()
            self.filter_modules.clear()
            IPluginRegistry.plugin_registries.clear()
            plugins_path = PluginUtility.filter_plugins_paths(
                self.plugins_package)
            package_name = os.path.basename(
                os.path.normpath(self.plugins_package))
            self.__search_for_plugins_in(plugins_path, package_name)

    @staticmethod
    def register_plugin_annotation(module: type) -> AnnotationPluginCore:
        """
        Create a plugin instance from the given module
        :param module: module to initialize
        :param logger: logger for the module to use
        :return: a high level plugin
        """
        return module()

    @staticmethod
    def register_plugin_filter(module: type) -> FilterPluginCore:
        """
        Create a plugin instance from the given module
        :param module: module to initialize
        :param logger: logger for the module to use
        :return: a high level plugin
        """
        return module()

    @staticmethod
    def hook_plugin_annotation(plugin: AnnotationPluginCore):
        """
        Return a function accepting commands.
        """
        return plugin.invoke

    @staticmethod
    def hook_plugin_filter(plugin: FilterPluginCore):
        """
        Return a function accepting commands.
        """
        return plugin.invoke
