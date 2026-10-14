from qiskit import QuantumCircuit

# Oracle that marks |11>
oracle = QuantumCircuit(2, name="oracle")
oracle.cz(0, 1)

# Diffusion operator
diffuser = QuantumCircuit(2, name="diffuser")
diffuser.h([0, 1])
diffuser.z([0, 1])
diffuser.cz(0, 1)
diffuser.h([0, 1])

grover = QuantumCircuit(2, 2)
grover.h([0, 1])
grover.compose(oracle, inplace=True)
grover.compose(diffuser, inplace=True)
grover.measure([0, 1], [0, 1])
