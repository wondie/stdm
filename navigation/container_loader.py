"""
/***************************************************************************
Name                 : Module Loader
Description          : Loads content items (toolbars, stackwidget items, etc.)
                        based on the approved role(s) of the item
Date                 : 27/May/2013
copyright            : (C) 2013 by John Gitau
email                : gkahiu@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from PyQt4.QtGui import QToolBar, QMenu, QListWidget, QApplication
from PyQt4.QtCore import QObject, pyqtSignal

from collections import OrderedDict

from utils import get_index
import stdm.data
from stdm.data import Content, Role
from .content_group import ContentGroup
from security import Authorizer, SecurityException


class QtContainerLoader(QObject):
    """
    Loads actions to the specified container based on the approved roles.
    The loader registers new modules if they do not exist
    If an actionRef parameter is specified then the action will all be added
    before the reference action in the corresponding container widget.
    """
    authorized = pyqtSignal(Content)
    finished = pyqtSignal()
    # contentAdded = pyqtSignal(Content)

    def __init__(self, parent, container, action_ref=None, register=False):
        QObject.__init__(self, parent)
        self._container = container
        self._register = register
        self._action_reference = action_ref
        self._content_groups = OrderedDict()
        self._widgets = []
        self._user_name = stdm.data.app_dbconn.user.UserName
        self._authorizer = Authorizer(stdm.data.app_dbconn.user.UserName)
        self._iter = 0
        self._separator_action = None

    def add_content(self, content, parents=None):
        """
        Add ContentGroup and its corresponding parent if available.
        :param content:
        :param parents:
        """
        self._content_groups[content] = parents

        # Connect content group signals
        if isinstance(content, ContentGroup):
            content.content_authorized.connect(self._on_content_authorized)

    def add_contents(self, contentGroups, parents=None):
        """
        Append multiple content groups which share the same parent widgets.
        :param contentGroups:
        :param parents:
        """
        for cg in contentGroups:
            self.add_content(cg, parents)

    def load_content(self):
        """
        Add defined items in the specified container.
        """
        # If the user does not belong to any STDM group then the system will
        # raise an error so gracefully terminate
        user_roles = self._authorizer.userRoles

        if len(user_roles) == 0:
            msg = QApplication.translate(
                "ModuleLoader", "'%s' must be a member of at least one STDM "
                                "role in order to access the "
                                "modules.\nPlease contact the system "
                                "administrator for more information." %
                                (self._user_name,))
            raise SecurityException(msg)

        for k, v in self._content_groups.iteritems():
            # Generic content items
            if not isinstance(k, ContentGroup):
                self._add_item_to_container(k)

            else:
                # Assert permissions then add to container
                allowedContent = k.check_content_access()

                if len(allowedContent) > 0:
                    if v is None:
                        # if there is no parent then add directly to container
                        # after asserting permissions
                        self._add_item_to_container(k.container_item())
                    else:
                        v[0].addAction(k.container_item())
                        self._insert_widget_to_container(v[1])

                    # Raise signal to indicate that an STDMAction has been
                    # added to the container
                    # self.contentAdded.emit(k)

        # Add separator
        if isinstance(self._container, QToolBar) or isinstance(
                self._container, QMenu):
            self._separator_action = self._container.insertSeparator(
                self._action_reference)

        # Remove consecutive separators
        self._rem_consecutive_separators()

        # Emit signal on finishing to load content
        self.finished.emit()

    def _on_content_authorized(self, content):
        """
        Slot raised when a content item has been approved in the content group.
        The signal is propagated to the caller.
        :param content:
        """
        self.authorized.emit(content)

    def _rem_consecutive_separators(self):
        """
        Removes consecutive separator actions.
        """
        actions = self._container.actions()

        for i, act in enumerate(actions):
            prev_idx = i - 1
            if prev_idx >= 0:
                prev_act = actions[prev_idx]
                if prev_act.isSeparator() and act.isSeparator():
                    self._container.removeAction(act)

        # Check if first action is separator and if so, remove it
        if len(actions) > 0:
            first_act = actions[0]
            if first_act.isSeparator():
                self._container.removeAction(first_act)

    def _add_item_to_container(self, content):
        """
        Adds items to specific container
        :param content:
        """
        if isinstance(self._container, QToolBar) or isinstance(
                self._container, QMenu):
            if self._action_reference is not None:
                self._container.insertAction(self._action_reference, content)
            else:
                self._container.addAction(content)

        elif isinstance(self._container, QListWidget):
            self._container.insertItem(self._iter, content)
            self._iter += 1

    def _insert_widget_to_container(self, widget):
        """
        This method inserts the parent widget to the container for those
        actions that have parents defined. But it ensures that only one
        instance of the parent widget is inserted.
        :param widget:
        """
        obj_name = widget.objectName()
        # Determine if the widget is already in the container
        if get_index(self._widgets, obj_name) == -1:
            if isinstance(self._container, QToolBar):
                self._container.insertWidget(self._action_reference, widget)
            elif isinstance(self._container, QMenu):
                self._container.insertMenu(self._action_reference, widget)

            self._widgets.append(obj_name)

    def unload_content(self):
        """
        Remove all items in the container.
        """
        for k, v in self._content_groups.iteritems():
            if isinstance(self._container, QToolBar) or isinstance(
                    self._container, QMenu):
                # If there is a parent then delete the widget
                if v is not None:
                    v[1].setParent(None)
                else:
                    if isinstance(k, ContentGroup):
                        k = k.container_item()

                    self._container.removeAction(k)

        # Remove separator
        if self._separator_action is not None:
            self._container.removeAction(self._separator_action)
