#!/usr/bin/env python
import time
import datetime as dt
import mimetypes
import os
from pathlib import Path

import pyudev
import xbmc
import xbmcaddon
import xbmcgui

context = pyudev.Context()
addon = xbmcaddon.Addon("script.auto_import")
addonname = addon.getAddonInfo('name')

old_mounts = []


class Stats:
    def __init__(self):
        self.total_files = 0
        self.total_size = 0
        self.copied = 0
        self.copied_size = 0
        self.last_file = ""

    def update(self, file, size):
        self.copied = self.copied + 1
        self.copied_size = self.copied_size + size
        self.last_file = file


_stats = Stats()
_progress_dialog = None


def pop_up(title, msg):
    xbmc.log('Eecuting built-in.')
    xbmc.executebuiltin('Notification(' + title + ',' + msg + ')')


def find_new_mounts():
    global old_mounts
    new_mounts = find_mount_points("/media")
    rval = []

    for m in new_mounts:
        if m not in old_mounts:
            rval.append(m)

    old_mounts = new_mounts
    return rval


def initialize():
    global old_mounts
    old_mounts = find_mount_points("/media")


def find_mount_points(path):
    rval = []

    files = os.listdir(path)
    for file in files:
        abs_path = os.path.join(path, file)
        if os.path.ismount(abs_path):
            rval.append(abs_path)
        elif os.path.isdir(abs_path):
            rval = rval + find_mount_points(abs_path)
        else:
            # Just a file
            pass

    return rval


def copy_file(src_p, dst_p):
    global _stats
    buffer_size = 1024 * 4
    src = str(src_p.absolute())
    dst = str(dst_p.absolute())

    msg = str(src) + " to " + str(dst)
    xbmc.log("Copying file: " + msg, xbmc.LOGINFO)

    with open(src, "rb") as src_f, open(dst, "wb") as dst_f:
        while True:
            buf = src_f.read(buffer_size)
            if not buf:
                break
            dst_f.write(buf)
            _stats.update(src_p, len(buf))
            update_progress()


def find_files(src_path, mime_prefixes):
    """
    Copy everything in base_path that ends with extension to dest.

    params are Paths
    """
    rval = []
    if not src_path.is_dir():
        xbmc.log(str(src_path) + " is not a directory. Skipping.", xbmc.LOGINFO)

    for p in src_path.iterdir():
        if p.is_dir():
            # Recurse.
            rval = rval + find_files(p, mime_prefixes)
        else:
            for mime_prefix in mime_prefixes:
                mime_type = mimetypes.guess_type(str(p.absolute()))
                if mime_type is not None and mime_type[0] is not None and mime_type[0].startswith(mime_prefix):
                    xbmc.log("p: " + str(p), xbmc.LOGINFO)
                    rval.append(p)
    return rval


def gather_stats(all_files):
    global _stats
    _stats.total_files = len(all_files)
    for file in all_files:
        _stats.total_size = _stats.total_size + file.stat().st_size
    xbmc.log("Total size: " + str(_stats.total_size), xbmc.LOGINFO)


def copy_all(src_path, dst_path, mime_prefix):
    """
    Copy everything in base_path that ends with extension to dest.

    params are Paths
    """
    if not src_path.is_dir():
        xbmc.log(str(src_path) + " is not a directory. Skipping.", xbmc.LOGINFO)

    for p in src_path.iterdir():
        if p.is_dir():
            # Recurse.
            copy_all(p, dst_path, mime_prefix)
        else:
            mime_type = mimetypes.guess_type(str(p.absolute()))
            if mime_type is not None and mime_type[0] is not None and mime_type[0].startswith(mime_prefix):
                xbmc.log("p: " + str(p), xbmc.LOGINFO)
                copy_file(p, Path(str(dst_path.absolute()) + "/" + str(p.name)))


def update_progress():
    global _progress_dialog
    if _progress_dialog is not None:
        pct = _stats.copied_size / _stats.total_size
        pct_i = int(pct * 100)
        _progress_dialog.update(pct_i, str(_stats.last_file.name))


def run():
    global _stats, _progress_dialog
    now = dt.datetime.now()
    xbmc.log("auto_import: Polling for new things: " + str(now), xbmc.LOGDEBUG)

    new_mounts = find_new_mounts()
    if len(new_mounts) > 0:
        _stats = Stats()
        pop_up("Found a new storage device", "Copying files...")
        _progress_dialog = xbmcgui.DialogProgress()
        _progress_dialog.create('Copying Files', 'Initializing script...')
        for mount_point in new_mounts:
            mount_path = Path(mount_point)

            all_files = find_files(mount_path, ["image", "video"])
            gather_stats(all_files)

            dest = Path("/home/osmc/Pictures")
            copy_all(mount_path, dest, "image")

            dest = Path("/home/osmc/Videos")
            copy_all(mount_path, dest, "video")
        pop_up("Copying Files", "Done!")
        _progress_dialog.close()
