"""Repository entry point: python training/train_dualview.py --data DATA --output RUN."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vision'/'dualview'))
from train import main
if __name__=='__main__':main()
