"""Runs editor code in a separate process and reports the circuits it defines.

Reads source code on stdin and writes one JSON object to stdout. Running in a
child process means an infinite loop or a crash in user code can never freeze
the IDE; the parent simply kills the process after a timeout.
"""

import base64
import contextlib
import io
import json
import sys
import traceback

FILENAME = "<editor>"


def _error_line(exc):
    """Line number in the editor where the exception happened, if any."""
    if isinstance(exc, SyntaxError) and exc.filename == FILENAME:
        return exc.lineno
    line = None
    for frame in traceback.extract_tb(exc.__traceback__):
        if frame.filename == FILENAME:
            line = frame.lineno
    return line


def _describe(name, qc, style, fold):
    from qiskit.visualization import circuit_drawer
    import matplotlib.pyplot as plt

    info = {
        "name": name,
        "num_qubits": qc.num_qubits,
        "num_clbits": qc.num_clbits,
        "depth": qc.depth(),
        "size": qc.size(),
        "ops": {k: int(v) for k, v in qc.count_ops().items()},
        "text": str(circuit_drawer(qc, output="text", fold=-1)),
        "png": None,
        "draw_error": None,
    }
    try:
        fig = circuit_drawer(qc, output="mpl", style=style, fold=fold)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        info["png"] = base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:  # e.g. pylatexenc missing; text diagram still works
        info["draw_error"] = f"{type(exc).__name__}: {exc}"
    return info


def main():
    request = json.loads(sys.stdin.read())
    source = request["source"]
    style = request.get("style", "iqp")
    fold = request.get("fold", -1)
    # Let the code import modules that sit next to the file being edited.
    sys.path.insert(0, request.get("cwd") or ".")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.show = lambda *a, **k: None

    result = {"ok": True, "circuits": [], "stdout": "", "error": None, "error_line": None}
    out = io.StringIO()
    namespace = {"__name__": "__qiskit_ide_preview__"}
    try:
        code = compile(source, FILENAME, "exec")
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(code, namespace)
    except BaseException as exc:
        result["ok"] = False
        if isinstance(exc, SyntaxError):
            result["error"] = f"{type(exc).__name__}: {exc.msg}"
        else:
            result["error"] = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        result["error_line"] = _error_line(exc)

    # Show whatever circuits exist, even if the script failed part-way:
    # this keeps the diagram useful while you are mid-edit.
    try:
        from qiskit import QuantumCircuit

        seen = set()
        for name, value in list(namespace.items()):
            if isinstance(value, QuantumCircuit) and id(value) not in seen and not name.startswith("_"):
                seen.add(id(value))
                with contextlib.redirect_stdout(out):
                    result["circuits"].append(_describe(name, value, style, fold))
    except Exception as exc:
        result["ok"] = False
        result["error"] = result["error"] or f"{type(exc).__name__}: {exc}"

    result["stdout"] = out.getvalue()[-20000:]
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
