# Qiskit IDE

A desktop editor for Qiskit programs with a live circuit diagram.

- **Code editor**: Python syntax highlighting with Qiskit classes and gate calls emphasised, line numbers, auto-indent, bracket pairing, Tab/Shift+Tab block indent, Ctrl+/ to comment.
- **Live circuit diagram**: every `QuantumCircuit` your code defines is drawn as you type (half-second debounce). Pick a circuit from the dropdown, switch between the matplotlib diagram and a text drawing, change style (iqp, iqp-dark, clifford, textbook, bw), wrap long circuits, zoom with the buttons or Ctrl+scroll. Shows qubits, depth and gate counts.
- **Errors**: the failing line is highlighted in the editor and the message is shown under the diagram; the diagram keeps showing the circuit built up to the error.
- **Gate buttons**: H, X, Y, Z, S, T, RX/RY/RZ, CX, CZ, SWAP, CCX, barrier and measure insert code for the selected circuit below the cursor, with the qubit arguments selected so you can type over them.
- **Run (F5)**: runs the whole script and streams its output to the console. Shift+F5 stops it.
- **Files**: New, Open, Save, Save As, and bundled examples under File > Examples.

Preview code runs in a separate process with a 15 second limit, so a slow or hanging script never freezes the editor. It does execute your code on every edit, so turn off **Live preview** (status bar) for scripts with expensive side effects and use Ctrl+R to refresh by hand.

## Run it

Python 3.10+.

```bash
pip install -r requirements.txt
python -m qiskit_ide                 # starter circuit
python -m qiskit_ide path/to/file.py # open a file
```

## Layout

| File | Purpose |
| --- | --- |
| `qiskit_ide/app.py` | Main window, menus, files, run console |
| `qiskit_ide/editor.py` | Code editor widget |
| `qiskit_ide/highlighter.py` | Python + Qiskit syntax highlighting |
| `qiskit_ide/circuit_view.py` | Circuit pane (diagram, text, zoom, stats) |
| `qiskit_ide/gate_palette.py` | Gate buttons |
| `qiskit_ide/preview.py` | Debounced out-of-process rendering |
| `qiskit_ide/render_worker.py` | Child process: runs the code, draws its circuits |
| `examples/` | Example programs |
