from avaframe import runCom4FlowPy
import pathlib
import os

def run_simulation(avalanche_name):
    avalanche_dir = str(pathlib.Path(avalanche_name).resolve())
    
    print(f"Running FlowPy simulation for {avalanche_name} in {avalanche_dir}...")
    try:
        runCom4FlowPy.main(avalanche_dir)
        print("Simulation completed successfully.")
    except Exception as e:
        print(f"An error occurred during simulation: {e}")

if __name__ == "__main__":
    run_simulation('SkyPilotSubset5m')
