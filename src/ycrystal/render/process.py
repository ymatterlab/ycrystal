"""Non-blocking POV-Ray execution with QProcess (QtCore only; no window needed)."""

from __future__ import annotations

import subprocess
import time
from dataclasses import replace
from typing import Any

from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from shiboken6 import isValid

from ycrystal.render.jobs import RenderJob, RenderResult, finish_job, parse_progress
from ycrystal.render.povray import (
    background_startupinfo,
    hold_foreground,
    is_windows_engine,
    read_log,
    release_foreground,
    windows_engine_conflict,
)

WINDOWS_ENGINE_POLL_MS = 100
"""Interval in milliseconds at which a running POV-Ray for Windows is checked for exit,
and a waiting one for its turn."""

_engine_running: subprocess.Popen[bytes] | None = None
"""The POV-Ray for Windows that this program started last (it may have exited)."""

_engine_waiting: list[RenderProcess] = []
"""POV-Ray for Windows renders of this program waiting for their turn, oldest first."""


def _engine_busy() -> bool:
    """Return whether a POV-Ray for Windows started by this program still runs.

    Decided by the process itself, so that a render whose Qt object was deleted before
    it reported its end cannot hold up the others.
    """
    return _engine_running is not None and _engine_running.poll() is None


def _start_next_engine() -> None:
    """Start the oldest waiting POV-Ray for Windows render if none runs."""
    while _engine_waiting and not _engine_busy():
        process = _engine_waiting.pop(0)
        if isValid(process):  # its Qt object may have been deleted while it waited
            process._launch()


class RenderProcess(QObject):
    """Run POV-Ray for one job without blocking the Qt event loop.

    [`start`][ycrystal.render.process.RenderProcess.start] returns immediately; the
    render runs in a separate process. A running Qt event loop (``QCoreApplication``
    is sufficient; no window or display is needed) delivers the result through
    [`finished`][ycrystal.render.process.RenderProcess.finished].

    ``povray`` runs as a ``QProcess``, whose output gives the progress. POV-Ray for
    Windows prints nothing and must start minimised, which ``QProcess`` cannot ask for
    in PySide6: it runs as a ``subprocess.Popen`` that a timer checks every
    ``WINDOWS_ENGINE_POLL_MS`` (100 ms) for its exit, with the foreground held (see
    [`hold_foreground`][ycrystal.render.povray.hold_foreground]). It reports no
    progress until the final 100. Only one copy of it can run at a time, so this
    program's renders with it take turns: one started while another runs waits (and
    counts as running) until that one has finished. An open POV-Ray for Windows that
    keeps a single instance makes the render fail at once with an explanation (see
    [`windows_engine_conflict`][ycrystal.render.povray.windows_engine_conflict]).

    Parameters
    ----------
    job
        Prepared job; POV-Ray runs with ``job.directory`` as its working directory.
    executable
        POV-Ray executable.
    parent
        Qt parent object.

    Attributes
    ----------
    job
        The job being rendered. Its directory is not removed by this class; call
        ``job.cleanup()`` after `finished`.
    executable
        The POV-Ray executable.
    """

    finished = Signal(object)
    """Emitted exactly once with the [`RenderResult`][ycrystal.render.jobs.RenderResult].

    Also emitted if POV-Ray cannot be started or is cancelled; standard output and
    standard error are merged into the result's log.
    """

    progress = Signal(int)
    """Emitted with the render progress in percent whenever POV-Ray reports it.

    POV-Ray reports at intervals, so a successful render ends with an extra 100 if its
    last report was lower.
    """

    def __init__(self, job: RenderJob, executable: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.job = job
        self.executable = executable
        self._log: list[str] = []
        self._done = False
        self._cancelled = False
        self._started_at = 0.0
        self._last_percent = -1
        self._process: QProcess | None = None
        self._popen: subprocess.Popen[bytes] | None = None
        self._holds_foreground = False
        self._waiting = False
        if is_windows_engine(executable):
            self._poll_timer = QTimer(self)
            self._poll_timer.setInterval(WINDOWS_ENGINE_POLL_MS)
            self._poll_timer.timeout.connect(self._poll)
            return
        self._process = QProcess(self)
        self._process.setProgram(executable)
        self._process.setArguments(job.arguments(executable))
        self._process.setWorkingDirectory(str(job.directory))
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    def start(self) -> None:
        """Start POV-Ray and return immediately."""
        self._started_at = time.monotonic()
        if self._process is not None:
            self._process.start()
            return
        if _engine_busy() or _engine_waiting:
            self._waiting = True  # another POV-Ray for Windows runs: take turns
            _engine_waiting.append(self)
            self._poll_timer.start()  # checks for its turn
            return
        self._launch()

    def _launch(self) -> None:
        """Start POV-Ray for Windows now (its turn has come)."""
        global _engine_running
        self._waiting = False
        self._started_at = time.monotonic()
        conflict = windows_engine_conflict(self.executable)
        if conflict:
            self._failed_to_start(conflict)
            return
        self._holds_foreground = hold_foreground(self.executable)
        try:
            self._popen = subprocess.Popen(
                [self.executable, *self.job.arguments(self.executable)],
                cwd=self.job.directory,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=background_startupinfo(self.executable),
            )
        except OSError as exc:
            self._failed_to_start(f"Could not start POV-Ray ({self.executable}): {exc}")
            return
        _engine_running = self._popen
        self._poll_timer.start()

    def is_running(self) -> bool:
        """Return whether the POV-Ray process is waiting for its turn, starting, or running.

        False from the moment [`finished`][ycrystal.render.process.RenderProcess.finished]
        is emitted, even though Qt may still be tidying up the process.
        """
        if self._done:
            return False
        if self._process is not None:
            return self._process.state() != QProcess.ProcessState.NotRunning
        # Running until the poll reports the exit, as QProcess is until it emits finished.
        return self._waiting or self._popen is not None

    def cancel(self) -> None:
        """Stop a running POV-Ray process.

        [`finished`][ycrystal.render.process.RenderProcess.finished] is then emitted
        with ``ok=False``, ``cancelled=True``, and ``returncode=None``. Does nothing if
        the process is not running.
        """
        if not self.is_running():
            return
        self._cancelled = True
        if self._process is not None:
            self._process.kill()
            return
        if self._waiting:
            _engine_waiting.remove(self)
            self._waiting = False
        elif self._popen is not None:
            self._popen.kill()
            try:
                self._popen.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover - a process that ignores kill
                pass
        # At once, not at the next poll: the window may delete this object right after.
        self._finish(None)

    def _read_output(self) -> None:
        if self._process is None:
            return
        text = bytes(self._process.readAllStandardOutput().data()).decode("utf-8", errors="replace")
        if text:
            self._log.append(text)
            percent = parse_progress(text)
            if percent is not None:
                self._last_percent = percent
                self.progress.emit(percent)

    def _poll(self) -> None:
        if self._done:
            return
        if self._waiting:
            while _engine_waiting and not isValid(_engine_waiting[0]):
                _engine_waiting.pop(0)  # deleted while it waited
            if _engine_waiting and _engine_waiting[0] is self and not _engine_busy():
                _engine_waiting.pop(0)
                self._launch()
            return
        if self._popen is None:
            return
        returncode = self._popen.poll()
        if returncode is not None:
            self._finish(returncode)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        crashed = exit_status != QProcess.ExitStatus.NormalExit
        self._finish(None if crashed else exit_code)

    def _finish(self, returncode: int | None) -> None:
        if self._done:
            return
        self._done = True
        self._stop_watching()
        self._read_output()
        elapsed = time.monotonic() - self._started_at
        log = "".join(self._log) + read_log(self.job.directory)  # POV-Ray for Windows
        if self._cancelled:
            result = RenderResult(False, None, log, None, "Render cancelled.", True, elapsed)
        else:
            result = replace(finish_job(self.job, returncode, log), elapsed=elapsed)
            if result.ok and self._last_percent < 100:
                self.progress.emit(100)  # the last interval report may predate completion
        self.finished.emit(result)
        if self._process is None:
            _start_next_engine()

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart and self._process is not None:
            self._failed_to_start(
                f"Could not start POV-Ray ({self.executable}): {self._process.errorString()}"
            )

    def _failed_to_start(self, message: str) -> None:
        if self._done:
            return
        self._done = True
        self._stop_watching()
        self.finished.emit(RenderResult(False, None, "".join(self._log), None, message))
        if self._process is None:
            _start_next_engine()

    def _stop_watching(self) -> None:
        """Stop the exit check, give up the turn, and end the foreground hold.

        Only POV-Ray for Windows has any of these.
        """
        global _engine_running
        if self._process is None:
            self._poll_timer.stop()
            if _engine_running is not None and _engine_running is self._popen:
                _engine_running = None
        if self._holds_foreground:
            self._holds_foreground = False
            release_foreground()


class RenderQueue(QObject):
    """Run render jobs one at a time; a newer job supersedes older work.

    Used for previews: [`submit`][ycrystal.render.process.RenderQueue.submit] while a
    job runs cancels the running job and keeps only the newest submission, which starts
    when the cancelled process has exited. At most one POV-Ray process runs per queue.

    Each job carries a caller-defined tag (Ycrystal uses the scene revision), returned
    with its result so that the caller can discard stale results.

    Parameters
    ----------
    parent
        Qt parent object.
    """

    started = Signal(object)
    """Emitted with the tag when a job's process starts."""

    finished = Signal(object, object)
    """Emitted with ``(RenderResult, tag)`` for every job that ran, including cancelled
    ones. The job directory, and the image in it, is removed after the connected slots
    return; load or copy the image inside the slot."""

    progress = Signal(int)
    """Render progress in percent of the running job."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._current: RenderProcess | None = None
        self._current_tag: Any = None
        self._pending: tuple[RenderJob, str, Any] | None = None

    def submit(self, job: RenderJob, executable: str, tag: Any) -> None:
        """Run ``job`` now, or after cancelling the running job.

        A pending job that has not started yet is discarded (its directory removed).
        """
        if self._pending is not None:
            self._pending[0].cleanup()
            self._pending = None
        if self._current is not None and self._current.is_running():
            self._pending = (job, executable, tag)
            self._current.cancel()
        else:
            self._start(job, executable, tag)

    def cancel(self) -> None:
        """Discard the pending job and stop the running one."""
        if self._pending is not None:
            self._pending[0].cleanup()
            self._pending = None
        if self._current is not None:
            self._current.cancel()

    def is_busy(self) -> bool:
        """Return whether a job is running or waiting."""
        running = self._current is not None and self._current.is_running()
        return running or self._pending is not None

    @property
    def current_tag(self) -> Any:
        """Tag of the running job, or ``None``."""
        return self._current_tag if self._current is not None else None

    def _start(self, job: RenderJob, executable: str, tag: Any) -> None:
        process = RenderProcess(job, executable, self)
        process.finished.connect(self._on_finished)
        process.progress.connect(self.progress.emit)
        self._current, self._current_tag = process, tag
        process.start()
        self.started.emit(tag)

    def _on_finished(self, result: RenderResult) -> None:
        process, tag = self._current, self._current_tag
        self._current, self._current_tag = None, None
        try:
            self.finished.emit(result, tag)
        finally:
            if process is not None:
                process.job.cleanup()
                process.deleteLater()
        if self._pending is not None:
            job, executable, pending_tag = self._pending
            self._pending = None
            self._start(job, executable, pending_tag)
