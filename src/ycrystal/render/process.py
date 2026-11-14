"""Non-blocking POV-Ray execution with QProcess (QtCore only; no window needed)."""

from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, Signal

from ycrystal.render.jobs import RenderJob, RenderResult, finish_job


class RenderProcess(QObject):
    """Run one :class:`RenderJob`; emits :attr:`finished` with a :class:`RenderResult`."""

    finished = Signal(object)

    def __init__(self, job: RenderJob, executable: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.job = job
        self.executable = executable
        self._log: list[str] = []
        self._done = False
        self._process = QProcess(self)
        self._process.setProgram(executable)
        self._process.setArguments(job.arguments())
        self._process.setWorkingDirectory(str(job.directory))
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    def start(self) -> None:
        self._process.start()

    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def cancel(self) -> None:
        if self.is_running():
            self._process.kill()

    def _read_output(self) -> None:
        data = self._process.readAllStandardOutput().data()
        self._log.append(bytes(data).decode("utf-8", errors="replace"))

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if self._done:
            return
        self._done = True
        self._read_output()
        crashed = exit_status != QProcess.ExitStatus.NormalExit
        result = finish_job(self.job, None if crashed else exit_code, "".join(self._log))
        self.finished.emit(result)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart and not self._done:
            self._done = True
            message = f"Could not start POV-Ray ({self.executable}): {self._process.errorString()}"
            self.finished.emit(RenderResult(False, None, "".join(self._log), None, message))
