import sqlite3
import pandas as pd
import numpy as np
from faker import Faker

def generate_quantum_data(num_records=50):
    """Generate synthetic quantum simulation data"""
    fake = Faker()
    np.random.seed(42)
    
    # Simulation types and parameters
    sim_types = ['VQE', 'QAOA', 'Grover', 'Shor', 'QFT']
    backend_types = ['Statevector', 'QASM', 'Pulse']
    
    data = []
    for _ in range(num_records):
        record = {
            'simulation_id': fake.uuid4(),
            'algorithm': np.random.choice(sim_types),
            'qubits': np.random.randint(2, 28),
            'depth': np.random.randint(5, 100),
            'backend': np.random.choice(backend_types),
            'runtime_ms': np.random.lognormal(4, 1.2),
            'accuracy': np.random.uniform(0.7, 0.99),
            'date_run': fake.date_between(start_date='-1y'),
            'parameters': str({fake.word(): np.random.uniform() for _ in range(3)})
        }
        data.append(record)
    
    return pd.DataFrame(data)

def save_to_database(df):
    """Save data to SQLite database"""
    conn = sqlite3.connect('quantum_sims.db')
    df.to_sql('simulations', conn, if_exists='replace', index=False)
    conn.close()

if __name__ == '__main__':
    df = generate_quantum_data(100)
    save_to_database(df)
    print("Generated 100 quantum simulation records in quantum_sims.db")