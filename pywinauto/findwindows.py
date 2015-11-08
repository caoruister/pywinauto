# GUI Application automation and testing library
# Copyright (C) 2015 Intel Corporation
# Copyright (C) 2010 Mark Mc Mahon
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public License
# as published by the Free Software Foundation; either version 2.1
# of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
#    Free Software Foundation, Inc.,
#    59 Temple Place,
#    Suite 330,
#    Boston, MA 02111-1307 USA

"""Provides functions for iterating and finding windows

"""
from __future__ import unicode_literals

import re
import ctypes

from . import sysinfo
from . import six
from . import win32functions
from . import win32structures
from . import handleprops
from . import findbestmatch
from . import controls
from .elementInfo import NativeElementInfo
from .UIAElementInfo import UIAElementInfo, _UIA_dll, _iuia, _treeScope

# TODO: we should filter out invalid windows before returning

#=========================================================================
class WindowNotFoundError(Exception):
    "No window could be found"
    pass

#=========================================================================
class WindowAmbiguousError(Exception):
    "There was more then one window that matched"
    pass



#=========================================================================
def find_window(**kwargs):
    """Call findwindows and ensure that only one window is returned

    Calls find_windows with exactly the same arguments as it is called with
    so please see find_windows for a description of them."""
    if sysinfo.UIA_support:
        windows = find_elements(**kwargs)
    else:
        windows = find_windows(**kwargs)

    if not windows:
        raise WindowNotFoundError()

    if len(windows) > 1:
        #for w in windows:
        #    print "ambig", handleprops.classname(w), \
        #    handleprops.text(w), handleprops.processid(w)
        exception =  WindowAmbiguousError(
            "There are %d windows that match the criteria %s"% (
            len(windows),
            six.text_type(kwargs),
            )
        )

        exception.windows = windows
        raise exception

    return windows[0]

#=========================================================================
def find_elements(class_name = None,
                  class_name_re = None,
                  parent = None,
                  process = None,
                  title = None,
                  title_re = None,
                  top_level_only = True,
                  visible_only = True,
                  enabled_only = False,
                  best_match = None,
                  handle = None,
                  ctrl_index = None,
                  found_index = None,
                  predicate_func = None,
                  active_only = False,
                  control_id = None,
    ):
    """
    Find elements based on criteria passed in

    Possible values are:

    * **class_name**     Elements with this window class
    * **class_name_re**  Elements whose class match this regular expression
    * **parent**         Elements that are children of this
    * **process**        Elements running in this process
    * **title**          Elements with this Text
    * **title_re**       Elements whose Text match this regular expression
    * **top_level_only** Top level elements only (default=True)
    * **visible_only**   Visible elements only (default=True)
    * **enabled_only**   Enabled elements only (default=False)
    * **best_match**     Elements with a title similar to this
    * **handle**         The handle of the element to return
    * **ctrl_index**     The index of the child element to return
    * **found_index**    The index of the filtered out child lement to return
    * **active_only**    Active elements only (default=False)
    * **control_id**     Elements with this control id
    """

    # allow a handle to be passed in
    # if it is present - just return it
    if handle is not None:
        return [UIAElementInfo(handle), ]

    # check if parent is a handle of element (in case of searching native controls)
    if parent:
        if isinstance(parent, int):
            parent = UIAElementInfo(parent)

    if top_level_only:
        # find the top level elements
        elements = enum_elements()

        # if we have been given a parent
        if parent:
            elements = [elem for elem in elements if elem.parent == parent]

    # looking for child elements
    else:
        # if not given a parent look for all children of the desktop
        if not parent:
            parent = UIAElementInfo(None)

        # look for all children of that parent
        elements = parent.descendants

        # if the ctrl_index has been specified then just return
        # that control
        if ctrl_index is not None:
            return [elements[ctrl_index], ]

    if control_id is not None and elements:
        elements = [elem for elem in elements if elem.controlId == control_id]

    if active_only:
        # TODO: getting active windows is based on win32functions - needs rewriting
        gui_info = win32structures.GUITHREADINFO()
        gui_info.cbSize = ctypes.sizeof(gui_info)

        # get all the active elements (not just the specified process)
        ret = win32functions.GetGUIThreadInfo(0, ctypes.byref(gui_info))

        if not ret:
            raise ctypes.WinError()

        found_active = False
        for elem in elements:
            if elem.handle == gui_info.hwndActive:
                found_active = True
                elements = [elem, ]
                break
        if not found_active:
            elements = []

    # early stop
    if not elements:
        return elements

    if class_name is not None:
        elements = [elem for elem in elements if elem.className == class_name]

    if class_name_re is not None:
        class_name_regex = re.compile(class_name_re)
        elements = [elem for elem in elements if class_name_regex.match(elem.className)]

    if process is not None:
        elements = [elem for elem in elements if elem.processId == process]

    if title is not None:
        elements = [elem for elem in elements if elem.windowText == title]

    elif title_re is not None:
        title_regex = re.compile(title_re)
        def _title_match(w):
            t = w.windowText
            if t is not None:
                return title_regex.match(t)
            return False
        elements = [elem for elem in elements if _title_match(elem)]

    if visible_only:
        elements = [elem for elem in elements if elem.visible]

    if enabled_only:
        elements = [elem for elem in elements if elem.enabled]

    if best_match is not None:
        print('best_match = ', len(elements))
        wrapped_elems = []
        for elem in elements:
            try:
                # TODO: can't skip invalid handles because UIA element can have no handle
                # TODO: rewrite findbestmatch metod ? or use className and name check ?
                if elem.handle:
                #if elem.name and elem.name != '':
                    wrapped_elems.append(controls.WrapElement(elem))
            except controls.InvalidWindowElement:
                # skip invalid handles - they have dissapeared
                # since the list of elements was retrieved
                pass
        elements = findbestmatch.find_best_control_matches(
            best_match, wrapped_elems)

        # convert found elements back to UIAElementInfo
        # TODO: once again: UIA element can have no handle but findbestmatch returns all kinds of wrappers
        # TODO: (e.g. DialogWrapper or ListViewWrapper)
        # TODO: rewrite findbestmatch or write a method to be able to convert wrapped objects back to UIAElementInfo
        elements = [UIAElementInfo(elem.handle) for elem in elements]

    if predicate_func is not None:
        elements = [elem for elem in elements if predicate_func(elem)]

    # found_index is the last criterion to filter results
    if found_index is not None:
        if found_index < len(elements):
            elements = elements[found_index:found_index + 1]
        else:
            raise WindowNotFoundError(
                "found_index is specified as %d, but %d window/s found" %
                (found_index, len(elements))
            )

    return elements

#=========================================================================
def find_windows(class_name = None,
                class_name_re = None,
                parent = None,
                process = None,
                title = None,
                title_re = None,
                top_level_only = True,
                visible_only = True,
                enabled_only = False,
                best_match = None,
                handle = None,
                ctrl_index = None,
                found_index = None,
                predicate_func = None,
                active_only = False,
                control_id = None,
    ):
    """Find windows based on criteria passed in

    Possible values are:

    * **class_name**  Windows with this window class
    * **class_name_re**  Windows whose class match this regular expression
    * **parent**    Windows that are children of this
    * **process**   Windows running in this process
    * **title**     Windows with this Text
    * **title_re**  Windows whose Text match this regular expression
    * **top_level_only** Top level windows only (default=True)
    * **visible_only**   Visible windows only (default=True)
    * **enabled_only**   Enabled windows only (default=False)
    * **best_match**  Windows with a title similar to this
    * **handle**      The handle of the window to return
    * **ctrl_index**  The index of the child window to return
    * **found_index** The index of the filtered out child window to return
    * **active_only** Active windows only (default=False)
    * **control_id**  Windows with this control id
   """

    # allow a handle to be passed in
    # if it is present - just return it
    if handle is not None:
        return [NativeElementInfo(handle), ]

    if top_level_only:
        # find the top level windows
        windows = enum_windows()

        # if we have been given a parent
        if parent:
            windows = [win for win in windows
                if handleprops.parent(win) == parent]

    # looking for child windows
    else:
        # if not given a parent look for all children of the desktop
        if not parent:
            parent = win32functions.GetDesktopWindow()

        # look for all children of that parent
        windows = handleprops.children(parent)

        # if the ctrl_index has been specified then just return
        # that control
        if ctrl_index is not None:
            return [NativeElementInfo(windows[ctrl_index])]

    if control_id is not None and windows:
        windows = [win for win in windows if
            handleprops.controlid(win) == control_id]

    if active_only:
        gui_info = win32structures.GUITHREADINFO()
        gui_info.cbSize = ctypes.sizeof(gui_info)

        # get all the active windows (not just the specified process)
        ret = win32functions.GetGUIThreadInfo(0, ctypes.byref(gui_info))

        if not ret:
            raise ctypes.WinError()

        if gui_info.hwndActive in windows:
            windows = [gui_info.hwndActive]
        else:
            windows = []

    # early stop
    if not windows:
        return windows

    if class_name is not None:
        windows = [win for win in windows
            if class_name == handleprops.classname(win)]

    if class_name_re is not None:
        class_name_regex = re.compile(class_name_re)
        windows = [win for win in windows
            if class_name_regex.match(handleprops.classname(win))]

    if process is not None:
        windows = [win for win in windows
            if handleprops.processid(win) == process]

    if title is not None:
        windows = [win for win in windows
            if title == handleprops.text(win)]

    elif title_re is not None:
        title_regex = re.compile(title_re)
        def _title_match(w):
            t = handleprops.text(w)
            if t is not None:
                return title_regex.match(t)
            return False
        windows = [win for win in windows if _title_match(win)]

    if visible_only:
        windows = [win for win in windows if handleprops.isvisible(win)]

    if enabled_only:
        windows = [win for win in windows if handleprops.isenabled(win)]

    if best_match is not None:
        wrapped_wins = []

        for win in windows:
            try:
                wrapped_wins.append(controls.WrapHandle(win))
            except controls.InvalidWindowHandle:
                # skip invalid handles - they have dissapeared
                # since the list of windows was retrieved
                pass
        windows = findbestmatch.find_best_control_matches(
            best_match, wrapped_wins)

        # convert window back to handle
        windows = [win.handle for win in windows]

    if predicate_func is not None:
        windows = [win for win in windows if predicate_func(win)]

    # found_index is the last criterion to filter results
    if found_index is not None:
        if found_index < len(windows):
            windows = windows[found_index:found_index+1]
        else:
            raise WindowNotFoundError(
                "found_index is specified as %d, but %d window/s found" % 
                (found_index, len(windows)) 
                )

    return [NativeElementInfo(handle) for handle in windows]

#=========================================================================
def enum_windows():
    "Return a list of handles of all the top level windows"
    windows = []

    # The callback function that will be called for each HWND
    # all we do is append the wrapped handle
    def EnumWindowProc(hwnd, lparam):
        "Called for each window - adds handles to a list"
        windows.append(hwnd)
        return True

    # define the type of the child procedure
    enum_win_proc = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_long, ctypes.c_long)

    # 'construct' the callback with our function
    proc = enum_win_proc(EnumWindowProc)

    # loop over all the children (callback called for each)
    win32functions.EnumWindows(proc, 0)

    # return the collected wrapped windows
    return windows

#=========================================================================
def enum_elements():
    "Return a list of UIAElementInfo objects of all the top level windows using UIA functions"
    # TODO: enum_elements() returns UIAElementInfo's from handles from enum_windows()
    # TODO: enum_windows() returns 100+ handles
    # TODO: what is enum_windows() supposed to return? all top-level controls from all windows?
    windows = enum_windows()
    return [UIAElementInfo(handle) for handle in windows]
