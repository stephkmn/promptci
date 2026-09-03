"""Code execution grader (M3). Not implemented yet.

Plan, so that the milestone has a starting point:

- The case's `inputs` hold the function prompt (`prompt`) and the test harness
  (`test`, `entry_point`) in HumanEval's format. The model output is the candidate
  completion. The program to run is ``prompt + completion + "\\n" + test +
  f"\\ncheck({entry_point})"``.
- Run it with `subprocess.run([sys.executable, "-I", path], timeout=...)` in a fresh
  temporary directory, with ``cwd`` set to that directory, an empty environment
  (no PYTHONPATH, no HOME), and, on Linux/macOS, `resource.setrlimit` for CPU
  seconds, address space, and open files via `preexec_fn`.
- Network: there is no portable way to block it from Python alone. Document that.
  Optionally, on Linux, run under ``unshare -n`` if available.
- Score 1 if exit code 0 within the timeout, else 0. `details` carries stdout/stderr
  (truncated) and the reason (timeout, exception, nonzero exit).
- This is not a security sandbox. It protects against accidents (infinite loops,
  huge allocations), not against a hostile model. Say so in the README.

Options: `timeout_s` (default 10), `memory_mb` (default 512), `extra_setup` (code
prepended to every program, e.g. imports the tests assume).
"""

from __future__ import annotations

from typing import Any

from promptci.graders.base import Grader, GradeResult
from promptci.suite.schema import Case


class CodeExecGrader(Grader):
    type = "code_exec"

    def __init__(self, **options: Any):
        super().__init__(**options)
        self.timeout_s = float(options.get("timeout_s", 10.0))
        self.memory_mb = int(options.get("memory_mb", 512))

    async def agrade(self, output: str, case: Case) -> GradeResult:
        raise NotImplementedError("code_exec grader is implemented in milestone M3")

    def grade(self, output: str, case: Case) -> GradeResult:
        raise NotImplementedError("code_exec grader is implemented in milestone M3")
