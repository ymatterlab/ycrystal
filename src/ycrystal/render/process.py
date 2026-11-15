"""Non-blocking POV-Ray execution with QProcess (QtCore only; no window needed)."""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from PySide6.QtCore import QObject, QProcess, Signal

from ycrystal.render.jobs import RenderJob, RenderResult, finish_job, parse_progress


class RenderProcess(QObject):
    """Run POV-Ray for one job without blocking the Qt event loop.

    [`start`][ycrystal.render.process.RenderProcess.start] returns immediately; the
    render runs in a separate process. A running Qt event loop (``QCoreApplication``
    is sufficient; no window or display is needed) delivers the result through
    [`finished`][ycrystal.render.process.RenderProcess.finished].

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
    """Emitted with the render progress in percent whenever POV-Ray reports it."""

    def __init__(self, job: RenderJob, executable: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.job = job
        self.executable = executable
        self._log: list[str] = []
        self._done = False
        self._cancelled = False
        self._started_at = 0.0
        self._process = QProcess(self)
        self._process.setProgram(executable)
        self._process.setArguments(job.arguments())
        self._process.setWorkingDirectory(str(job.directory))
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    def start(self) -> None:
        """Start POV-Ray and return immediately."""
        self._started_at = time.monotonic()
        self._process.start()

    def is_running(self) -> bool:
        """Return whether the POV-Ray process is starting or running.

        False from the moment [`finished`][ycrystal.render.process.RenderProcess.finished]
        is emitted, even though Qt may still be tidying up the process.
        """
        return not self._done and self._process.state() != QProcess.ProcessState.NotRunning

    def cancel(self) -> None:
        """Stop a running POV-Ray process.

        [`finished`][ycrystal.render.process.RenderProcess.finished] is then emitted
        with ``ok=False``, ``cancelled=True``, and ``returncode=None``. Does nothing if
        the process is not running.
        """
        if self.is_running():
            self._cancelled = True
            self._process.kill()

    def _read_output(self) -> None:
        text = bytes(self._process.readAllStandardOutput().data()).decode("utf-8", errors="replace")
        if text:
            self._log.append(text)
            percent = parse_progress(text)
            if percent is not None:
                self.progress.emit(percent)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if self._done:
            return
        self._done = True
        self._read_output()
        elapsed = time.monotonic() - self._started_at
        log = "".join(self._log)
        if self._cancelled:
            result = RenderResult(False, None, log, None, "Render cancelled.", True, elapsed)
        else:
            crashed = exit_status != QProcess.ExitStatus.NormalExit
            result = replace(
                finish_job(self.job, None if crashed else exit_code, log), elapsed=elapsed
            )
        self.finished.emit(result)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart and not self._done:
            self._done = True
            message = f"Could not start POV-Ray ({self.executable}): {self._process.errorString()}"
            self.finished.emit(RenderResult(False, None, "".join(self._log), None, message))


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
