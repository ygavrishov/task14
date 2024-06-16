import sys

from dejavu import Dejavu
from dejavu.logic.recognizer.file_recognizer import FileRecognizer
from dejavu.logic.recognizer.microphone_recognizer import MicrophoneRecognizer

# load config from a JSON file (or anything outputting a python dictionary)
config = {
    "database": {
        "host": "db",
        "user": "postgres",
        "password": "password",
        "database": "dejavu"
    },
    "database_type": "postgres"
}

if __name__ == '__main__':

    # create a Dejavu instance
    djv = Dejavu(config)

    # Print the command-line arguments
    if len(sys.argv) > 1:
        results = djv.recognize(FileRecognizer, sys.argv[1])
        print(f"From file we recognized: {results}\n")
    else:
        print("No arguments provided.")
