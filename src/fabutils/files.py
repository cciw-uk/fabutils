from __future__ import annotations

import io
import re
from shlex import quote

from fabric.connection import Connection
from fabric.transfer import Transfer
from invoke.runners import Result

__all__ = [
    "append",
    "exists",
    "get_file_as_bytes",
    "put_file_from_bytes",
    "require_directory",
    "require_file",
    "is_file",
    "is_dir",
    "get_owner",
    "get_group",
    "get_mode",
]


def get(c: Connection, remote_filename: str, local_filename: str):
    return Transfer(c).get(local=local_filename, remote=remote_filename).local


def put(c: Connection, local_filename: str, remote_filename: str):
    Transfer(c).put(local=local_filename, remote=remote_filename)


def get_file_as_bytes(c: Connection, filename: str) -> bytes:
    store = io.BytesIO()
    Transfer(c).get(remote=filename, local=store, preserve_mode=False)
    return store.getvalue()


def put_file_from_bytes(
    c: Connection, filename: str, contents: bytes, mode: str | None = None, owner: str | None = None
):
    store = io.BytesIO()
    store.write(contents)
    result = Transfer(c).put(local=store, remote=filename, preserve_mode=False)
    remote_path = result.remote
    if mode is not None:
        c.run(f"chmod {mode} {quote(remote_path)}")
    if owner is not None:
        c.run(f"chmod {mode} {quote(remote_path)}")

    return result


def require_directory(c: Connection, path: str, owner: str = "", group: str = "", mode: str = ""):
    """
    Require a directory to exist.
    """

    if not is_dir(c, path):
        c.run(f"mkdir -p {quote(path)}", echo=True)

    _fix_perms(c, path, owner, group, mode)


def require_file(c: Connection, path: str, owner: str = "", group: str = "", mode: str = ""):
    """
    Require a file to exist
    """
    if not is_file(c, path):
        c.run(f"touch {quote(path)}", echo=True)

    _fix_perms(c, path, owner, group, mode)


def _fix_perms(c: Connection, path: str, owner: str, group: str, mode: str):
    # Ensure correct owner
    if (owner and get_owner(c, path) != owner) or (group and get_group(c, path) != group):
        if owner and group:
            c.run(f"chown {owner}:{group} {quote(path)}", echo=True)
        elif owner:
            c.run(f"chown {owner} {quote(path)}", echo=True)
        elif group:
            c.run(f"chgrp {group}:{group} {quote(path)}", echo=True)

    # Ensure correct mode
    if mode and get_mode(c, path).lstrip("0") != mode.lstrip("0"):
        c.run(f"chmod {mode} {quote(path)}", echo=True)


def is_file(c: Connection, path: str):
    """
    Check if a path exists, and is a file.
    """
    return c.run(f"test -f {quote(path)}", warn=True, hide="both").ok


def is_dir(c: Connection, path: str):
    """
    Check if a path exists, and is a directory.
    """
    return c.run(f"test -d {quote(path)}", warn=True, hide="both").ok


def get_owner(c: Connection, path: str):
    """
    Get the owner name of a file or directory.
    """
    result: Result = c.run(f"stat -c %U {quote(path)}", hide="both")
    return result.stdout.strip()


def get_group(c: Connection, path: str):
    """
    Get the group of a file or directory.
    """
    result: Result = c.run(f"stat -c %G {quote(path)}", hide="both")
    return result.stdout.strip()


def get_mode(c: Connection, path: str):
    """
    Get the mode/permissions of a file or directory.
    """
    result: Result = c.run(f"stat -c %a {quote(path)}", hide="both")
    return result.stdout.strip()


def exists(c: Connection, path: str):
    """
    Return True if given path exists on the current remote host.
    """
    result: Result = c.run(f'test -e "$(echo {quote(path)})"', hide="both", warn=True)
    return result.ok


def append(c: Connection, filename: str, text: str | list[str], partial=False, escape=True):
    """
    Append string (or list of strings) ``text`` to ``filename``.

    When a list is given, each string inside is handled independently (but in
    the order given.)

    If ``text`` is already found in ``filename``, the append is not run, and
    None is returned immediately. Otherwise, the given text is appended to the
    end of the given ``filename`` via e.g. ``echo '$text' >> $filename``.

    The test for whether ``text`` already exists defaults to a full line match,
    e.g. ``^<text>$``, as this seems to be the most sensible approach for the
    "append lines to a file" use case. You may override this and force partial
    searching (e.g. ``^<text>``) by specifying ``partial=True``.

    Because ``text`` is single-quoted, single quotes will be transparently
    backslash-escaped. This can be disabled with ``escape=False``.
    """
    # Normalize non-list input to be a list
    lines: list[str]
    if isinstance(text, str):
        lines = [text]
    else:
        lines = text
    for line in lines:
        regex = "^" + _escape_for_regex(line) + ("" if partial else "$")
        if line and exists(c, filename) and contains(c, filename, regex, escape=False):
            continue
        line = line.replace("'", r"'\\''") if escape else line
        c.run(f"echo '{line}' >> {quote(filename)}")


def contains(c: Connection, filename: str, text: str, exact=False, escape=True):
    """
    Return True if ``filename`` contains ``text`` (which may be a regex.)

    By default, this function will consider a partial line match (i.e. where
    ``text`` only makes up part of the line it's on). Specify ``exact=True`` to
    change this behavior so that only a line containing exactly ``text``
    results in a True return value.

    This function leverages ``egrep`` on the remote end (so it may not follow
    Python regular expression syntax perfectly), and skips the usual outer
    ``env.shell`` wrapper that most commands execute with.

    If ``escape`` is False, no extra regular expression related escaping is
    performed (this includes overriding ``exact`` so that no ``^``/``$`` is
    added.)
    """
    if escape:
        text = _escape_for_regex(text)
        if exact:
            text = f"^{text}$"
    egrep_cmd = f'egrep "{text}" "{quote(filename)}"'
    return c.run(egrep_cmd, hide=True, warn=True).ok


def _escape_for_regex(text):
    """Escape ``text`` to allow literal matching using egrep"""
    regex = re.escape(text)
    # Seems like double escaping is needed for \
    regex = regex.replace("\\\\", "\\\\\\")
    # Triple-escaping seems to be required for $ signs
    regex = regex.replace(r"\$", r"\\\$")
    # Whereas single quotes should not be escaped
    regex = regex.replace(r"\'", "'")
    return regex
