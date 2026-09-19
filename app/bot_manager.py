import os
import queue
import signal
import subprocess
import threading
import time

BOT_CMD = "bot"
LOADING_CMD = "loading"
STATUS_CMD = "status"
LOG_CMD = "log"
OUT = "out"
ERR = "err"
WARN = "warn"
SYSTEM = "system"
PIP = "pip"


def _event(kind, payload):
    return {"kind": kind, "payload": payload}


class BotManager:
    def __init__(self):
        self.events = queue.Queue()
        self.process = None
        self.interpreter = "python"
        self.token = ""
        self.max_restarts = 5
        self.restart_delay = 3
        self.started_at = None
        self.last_exit_code = None
        self._manual_stop = False
        self._lock = threading.Lock()

    @property
    def running(self):
        p = self.process
        return p is not None and p.poll() is None

    @property
    def uptime(self):
        if self.running and self.started_at:
            return time.time() - self.started_at
        return 0.0

    def _emit_log(self, text, stream=OUT):
        self.events.put(_event(LOG_CMD, {"stream": stream, "text": str(text)}))

    def _emit_status(self, text):
        self.events.put(_event(STATUS_CMD, text))

    def start(self, script_path, max_restarts, restart_delay, interpreter, token):
        with self._lock:
            if self.running:
                return
            self._manual_stop = False
            self.last_exit_code = None
            self.restart_count = 0
            self.interpreter = interpreter or "python"
            self.token = token or ""
            self.max_restarts = int(max_restarts)
            self.restart_delay = max(1, int(restart_delay))
            thread = threading.Thread(target=self._loop, args=(script_path,), daemon=True)
            thread.start()

    def stop(self, grace=6.0):
        with self._lock:
            self._manual_stop = True
        p = self.process
        if p is None or p.poll() is not None:
            self._emit_status("Stopped")
            return
        self._emit_log("Stopping bot...", SYSTEM)
        try:
            if os.name == "nt":
                p.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                p.send_signal(signal.SIGINT)
        except Exception:
            pass
        try:
            p.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            self._emit_log("Graceful stop timed out, killing process.", WARN)
            try:
                p.kill()
            except Exception:
                pass
        self._emit_status("Stopped")

    def restart(self, script_path, max_restarts, restart_delay, interpreter, token):
        self.stop(grace=4.0)
        time.sleep(0.4)
        self.start(script_path, max_restarts, restart_delay, interpreter, token)

    def run_command(self, command, cwd=None, label="task"):
        thread = threading.Thread(target=self._run_command, args=(command, cwd, label), daemon=True)
        thread.start()

    def _run_command(self, command, cwd, label):
        self._emit_log("$ " + " ".join(str(c) for c in command), SYSTEM)
        try:
            proc = subprocess.Popen(
                [str(c) for c in command],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=cwd,
            )
        except Exception as exc:
            self._emit_log(f"Failed to launch {label}: {exc}", ERR)
            return
        for line in iter(proc.stdout.readline, ""):
            self._emit_log(line.rstrip("\n"), PIP)
        code = proc.wait()
        if code == 0:
            self._emit_log(f"{label} finished successfully.", SYSTEM)
        else:
            self._emit_log(
                f"{label} failed with exit code {code}. Check the package name for typos. "
                f"Note: os, sys, re, json, math, time and similar are built-in Python modules - "
                f"they can never be installed via pip.",
                WARN,
            )

    def _loop(self, script_path):
        while True:
            if self._manual_stop:
                self._emit_status("Stopped")
                return
            self._emit_status("Starting")
            try:
                self._spawn(script_path)
            except Exception as exc:
                self._emit_log(f"Could not launch process: {exc}", ERR)
                self._emit_status("Crashed")
                return
            code = self.process.wait()
            self.last_exit_code = code
            if self._manual_stop:
                self._emit_status("Stopped")
                return
            if self.max_restarts < 0 or self.restart_count >= self.max_restarts:
                self._emit_log(f"Max restarts reached ({self.max_restarts}), giving up.", ERR)
                self._emit_status("Crashed")
                return
            self.restart_count += 1
            self._emit_log(
                f"Exited with code {code} - restart {self.restart_count}/{self.max_restarts} in {self.restart_delay}s.",
                WARN,
            )
            self._emit_status("Restarting...")
            waited = 0.0
            while waited < self.restart_delay:
                if self._manual_stop:
                    self._emit_status("Stopped")
                    return
                time.sleep(0.1)
                waited += 0.1

    def _spawn(self, script_path):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        if self.token:
            env["DISCORD_BOT_TOKEN"] = self.token
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        self.process = subprocess.Popen(
            [self.interpreter, script_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
            creationflags=creationflags,
        )
        self.started_at = time.time()
        threading.Thread(target=self._pump, args=(self.process.stdout, OUT), daemon=True).start()
        threading.Thread(target=self._pump, args=(self.process.stderr, ERR), daemon=True).start()
        self._emit_log("----- bot process started -----", SYSTEM)
        self._emit_status("Running")

    def _pump(self, stream, kind):
        for line in iter(stream.readline, ""):
            if self._manual_stop:
                break
            self._emit_log(line.rstrip("\n"), kind)