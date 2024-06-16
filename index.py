import json

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

    # Fingerprint all the mp3's in the directory we give it
    djv.fingerprint_directory("mytest", [".mp4"])
