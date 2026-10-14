from math import pi

from qiskit import QuantumCircuit


def qft(n):
    qc = QuantumCircuit(n, name="QFT")
    for target in reversed(range(n)):
        qc.h(target)
        for control in range(target):
            qc.cp(pi / 2 ** (target - control), control, target)
    for i in range(n // 2):
        qc.swap(i, n - i - 1)
    return qc


circuit = qft(4)
