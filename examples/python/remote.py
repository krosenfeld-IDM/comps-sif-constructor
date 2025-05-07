"""
This script runs remotely on COMPS.
Results that you want to *gather* should be saved in the file "results.json"
"""

import json
import cowsay

def main():
    with open('trial_index.json', 'r') as f:
        index = json.load(f)
    with open('trials.jsonl', 'r') as f:
        for cnt, line in enumerate(f):
            data = json.loads(line)
            if cnt == index['trial_index']:
                message = data['messages']
                cowsay.cow(message)
                s = cowsay.get_output_string('cow', message)
                with open("results.json", "w") as f:
                    import random
                    json.dump({"trial_index": cnt, "message": message + '!'}, f)
                break


if __name__ == '__main__':
    main() 