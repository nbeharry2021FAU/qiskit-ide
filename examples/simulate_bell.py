# Press F5 to run: samples the Bell circuit and prints the counts.
from qiskit import QuantumCircuit
from qiskit.primitives import StatevectorSampler

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
qc.measure_all()

result = StatevectorSampler().run([qc], shots=1000).result()
print(result[0].data.meas.get_counts())
