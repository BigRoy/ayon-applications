import os
import platform
import subprocess
from typing import Optional

from qtpy import QtWidgets, QtGui, QtCore

from ayon_applications import (
    Application,
    ApplicationManager,
)
from ayon_applications.utils import get_app_environments_for_context
from ayon_core.pipeline import LauncherAction
from ayon_core.style import load_stylesheet


def get_application_qt_icon(
        application: Application
) -> Optional[QtGui.QIcon]:
    """Return QtGui.QIcon for an Application"""
    # TODO: Improve workflow to get the icon, remove 'color' hack
    from ayon_core.tools.launcher.models.actions import get_action_icon
    from ayon_core.tools.utils.lib import get_qt_icon
    application.color = "white"
    return get_qt_icon(get_action_icon(application))


class DebugShell(LauncherAction):
    """Run any host environment in command line."""
    name = "debugshell"
    label = "Shell"
    icon = "terminal"
    color = "#e8770e"
    order = 10

    def is_compatible(self, selection) -> bool:
        return selection.is_task_selected

    def process(self, selection, **kwargs):
        # Get cursor position directly so the menu shows closer to where user
        # clicked because the get applications logic might take a brief moment
        pos = QtGui.QCursor.pos()

        # Get applications
        application_manager = ApplicationManager()
        applications = self.get_project_applications(
            application_manager, selection.project_entity)
        app = self.choose_app(applications, pos)
        if not app:
            return

        print(f"Retrieving environment for: {app.full_label}..")
        env = get_app_environments_for_context(selection.project_name,
                                               selection.folder_path,
                                               selection.task_name,
                                               app.full_name)

        # If an executable is found. Then add the parent folder to PATH
        # just so we can run the application easily from the command line.
        exe = app.find_executable()
        if exe:
            exe_path = exe._realpath()
            folder = os.path.dirname(exe_path)
            print(f"Appending to PATH: {folder}")
            env["PATH"] += os.pathsep + folder

        cwd = env.get("AYON_WORKDIR")
        if cwd:
            print(f"Setting Work Directory: {cwd}")

        print(f"Launching shell in environment of {app.full_label}..")
        self.launch_shell(application_manager,
                          project_name=selection.project_name,
                          folder_path=selection.folder_path,
                          task_name=selection.task_name,
                          env=env,
                          cwd=cwd)

    @staticmethod
    def choose_app(applications: list[Application],
                   pos: QtCore.QPoint) -> Optional[Application]:
        """Show menu to choose from list of applications"""
        menu = QtWidgets.QMenu()
        menu.setAttribute(QtCore.Qt.WA_DeleteOnClose)  # force garbage collect
        menu.setStyleSheet(load_stylesheet())

        # Sort applications
        applications.sort(key=lambda item: item.full_label)

        for app in applications:
            menu_action = QtWidgets.QAction(app.full_label, parent=menu)
            icon = get_application_qt_icon(app)
            if icon:
                menu_action.setIcon(icon)
            menu_action.setData(app)
            menu.addAction(menu_action)

        result = menu.exec_(pos)
        if result:
            return result.data()

    @staticmethod
    def get_project_applications(application_manager: ApplicationManager,
                                 project_entity: dict) -> list[Application]:
        """Return the enabled applications for the project"""
        # Filter to apps valid for this current project, with logic from:
        # `ayon_core.tools.launcher.models.actions.ApplicationAction.is_compatible`  # noqa
        applications = []
        for app_name in project_entity["attrib"].get("applications", []):
            app = application_manager.applications.get(app_name)
            if not app or not app.enabled:
                continue
            applications.append(app)

        return applications

    def launch_shell(self,
                     application_manager,
                     project_name,
                     folder_path,
                     task_name,
                     cwd,
                     env) -> list[str]:
        """Return the terminal executable to launch."""
        # TODO: Allow customization per user for this via AYON settings
        launch_context = application_manager.create_launch_context(
            "shell/main",
            project_name=project_name,
            folder_path=folder_path,
            task_name=task_name,
            env=env
        )
        launch_context.kwargs["cwd"] = cwd
        launch_context.kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        return application_manager.launch_with_context(launch_context)
